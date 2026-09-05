"""Faz 5a: 2×2 koşullu öneri toplama.

İki müdahaleyi bağımsız olarak açıp kapatır:

* **arch-context** — prompt'a mimari bağlam bloğu (katman, izinler, açık
  ihlaller, koku etiketleri) eklenir. H1'i test eder.
* **metric-rules** — prompt'a hesaplama kuralları eklenir. H2'yi test eder;
  FINDINGS-1'de yapısal metriklerde 0/7 yanılan modellerin **kapsam hatası**
  yaptığı gözlemine doğrudan müdahaledir.

Dört hücre birlikte, tek müdahalenin mi yoksa ikisinin birlikte mi işe
yaradığını ayırt etmeyi mümkün kılar.

**Bu aşama uygulama gerektirmez.** Kod değiştirilmez, yalnızca öneri toplanır.
Tahmin doğruluğu 5b'nin işidir ve yalnızca uygulama ile ölçülebilir.

**Önbellek koşulları karıştırmaz.** Anahtar prompt metninin tamamıdır; farklı
koşullar farklı prompt üretir, dolayısıyla farklı anahtar. Bir koşulun yanıtı
diğerine dönmez.

Kullanım:

    python experiments/run_advice_v2.py --models openai/gpt-oss-120b --plan
    python experiments/run_advice_v2.py --models m1,m2,m3 --delay 8
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from rlens import __version__  # noqa: E402
from rlens.advise.advisor import AdviceDocument, request_advice  # noqa: E402
from rlens.advise.context import build_context  # noqa: E402
from rlens.advise.selector import select_targets  # noqa: E402
from rlens.analysis.scanner import scan_project_with_sources  # noqa: E402
from rlens.config import Config, load_config  # noqa: E402
from rlens.llm.budget import Budget, BudgetExceeded  # noqa: E402
from rlens.llm.cache import ResponseCache  # noqa: E402
from rlens.providers import ProviderError, get_provider, load_env_file  # noqa: E402

DEFAULT_PROJECT = REPO_ROOT / "examples" / "layered_project"
DEFAULT_OUT = REPO_ROOT / "experiments" / "v2" / "runs"

#: 2×2 tasarım: (arch_context, metric_rules).
#:
#: Adlar dizin adı olur, bu yüzden kısa ve ayraçsızdır.
CONDITIONS: dict[str, tuple[bool, bool]] = {
    "plain": (False, False),
    "arch": (True, False),
    "rules": (False, True),
    "arch_rules": (True, True),
}

#: Protokol sabitleri. Sonuçlar görüldükten sonra **değiştirilmez**.
PROTOCOL = {"repetitions": 3, "top_n": 3}


def slug(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def output_path(out_dir: Path, condition: str, model: str, target: str, repetition: int) -> Path:
    return out_dir / condition / slug(model) / slug(target) / f"rep{repetition}.json"


def prepare_contexts(project: Path, config: Config, top_n: int):
    """Hedefleri seçer ve bağlamları kurar — **bir kez**, tüm koşullar için aynı.

    Koşullar arasındaki fark yalnızca prompt'tan gelmelidir. Bağlam yeniden
    kurulsaydı hedef seçimi veya kırpma farklılaşabilir ve fark müdahaleye
    değil gürültüye ait olurdu.
    """
    result = scan_project_with_sources(project, config)
    targets = select_targets(result.report, config, top_n)
    return [
        (
            target,
            build_context(
                target,
                result.modules,
                result.project_classes,
                config.advise.max_context_tokens,
            ),
        )
        for target in targets
    ]


def plan(contexts, models: list[str], repetitions: int, out_dir: Path):
    """Yapılacak çağrıların listesi; diskte olanlar atlanır."""
    pending, skipped = [], 0
    for condition in CONDITIONS:
        for model in models:
            for repetition in range(1, repetitions + 1):
                for target, context in contexts:
                    path = output_path(out_dir, condition, model, target.qualified_name, repetition)
                    if path.exists():
                        skipped += 1
                    else:
                        pending.append((condition, model, repetition, target, context))
    return pending, skipped


def run(
    project: Path,
    models: list[str],
    out_dir: Path,
    repetitions: int,
    top_n: int,
    delay: float,
    plan_only: bool,
    provider_factory=get_provider,
) -> int:
    config = load_config(search_from=project)
    contexts = prepare_contexts(project, config, top_n)
    pending, skipped = plan(contexts, models, repetitions, out_dir)

    total = len(CONDITIONS) * len(models) * repetitions * len(contexts)
    print(f"project    : {project}")
    print(f"targets    : {', '.join(t.qualified_name for t, _ in contexts)}")
    print(f"models     : {', '.join(models)}")
    print(f"conditions : {', '.join(CONDITIONS)}")
    print(f"protocol   : n={repetitions}, temperature={config.advise.temperature}")
    print(f"total      : {total} runs ({skipped} already on disk)\n")

    if plan_only:
        for condition, model, repetition, target, _ in pending:
            print(f"  {condition:<12}{model:<26}{target.qualified_name:<46}rep{repetition}")
        return 0
    if not pending:
        print("Nothing to do.")
        return 0

    load_env_file(project)
    cache = ResponseCache(replace(config.cache, directory=str(project / config.cache.directory)))
    # Bütçe koşu boyunca tek: 108 çağrılık bir deney tek `advise` çalıştırması
    # değildir, ama kaza eseri sınırsız çağrı yapmasını da istemeyiz.
    budget = Budget(replace(config.budget, max_calls_per_run=len(pending) + 10))

    made, failures = 0, []
    for index, (condition, model, repetition, target, context) in enumerate(pending, 1):
        arch_context, metric_rules = CONDITIONS[condition]
        run_config = replace(config, provider=replace(config.provider, model=model))
        scheme = run_config.arch.scheme if arch_context else None
        label = (
            f"[{index}/{len(pending)}] {condition} {model} {target.qualified_name} rep{repetition}"
        )
        print(label, flush=True)

        try:
            advice, warnings = request_advice(
                provider_factory(run_config.provider),
                context,
                run_config,
                cache=cache,
                budget=budget,
                scheme=scheme,
                metric_rules=metric_rules,
                # Tekrarlar birbirinin kopyası olmamalı: tuz olmadan rep2 ve
                # rep3 önbellekten döner ve varyans ölçülemez.
                cache_salt=f"rep{repetition}",
            )
        except (ProviderError, BudgetExceeded) as exc:
            print(f"  FAILED: {exc}")
            failures.append(f"{label}: {exc}")
            continue

        advice.warnings = warnings
        document = AdviceDocument(
            root=str(project.resolve()),
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            rlens_version=__version__,
            provider=run_config.provider.name,
            model=model,
            temperature=run_config.advise.temperature,
            advices=[advice],
        )
        payload = document.to_dict()
        # Koşul bilgisi rapora eklenir: çözümleme dizin adına güvenmemeli.
        payload["condition"] = condition
        payload["arch_context"] = arch_context
        payload["metric_rules"] = metric_rules

        destination = output_path(out_dir, condition, model, target.qualified_name, repetition)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        made += 1

        counts = [f"{len(advice.suggestions)} suggestion(s)"]
        rejected = sum(1 for s in advice.suggestions if s.is_rejected)
        if rejected:
            counts.append(f"{rejected} rejected")
        if advice.from_cache:
            counts.append("cached")
        print("  → " + ", ".join(counts))

        if index < len(pending) and delay > 0 and not advice.from_cache:
            time.sleep(delay)

    print(f"\n{made} run(s) written to {out_dir}")
    print(f"{budget.describe()} · {cache.describe()}")
    if failures:
        print(f"{len(failures)} failure(s):")
        for failure in failures:
            print(f"  {failure}")
    return made


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--models", required=True)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repetitions", type=int, default=PROTOCOL["repetitions"])
    parser.add_argument("--top-n", type=int, default=PROTOCOL["top_n"])
    parser.add_argument("--delay", type=float, default=5.0)
    parser.add_argument("--plan", action="store_true", help="List the calls and stop.")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        parser.error("at least one model id is required")

    run(
        project=args.project,
        models=models,
        out_dir=args.out,
        repetitions=args.repetitions,
        top_n=args.top_n,
        delay=args.delay,
        plan_only=args.plan,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
