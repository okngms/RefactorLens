"""Faz 5 / A parçası: öneri toplama.

Aynı hedefler için birden fazla modelden, her biri **n kez** öneri toplar ve ham
çıktıyı diske yazar. Kod değiştirilmez; bu aşama yalnızca veri biriktirir.

**Neden n tekrar?** Tek çıktıyla "modeller arasında fark var mı" sorusu
cevaplanamaz. Aynı modele aynı soruyu üç kez sorduğunuzda gelen cevaplar
birbirinden ne kadar farklıysa, iki model arasındaki farkın anlamlı sayılması
için o kadarını aşması gerekir.

**Neden kesintiye dayanıklı?** Ücretsiz katmanların günlük token limitleri
27 çağrıyı tek oturumda bitirmeye yetmeyebilir. Betik, çıktısı zaten yazılmış
kombinasyonları atlar; yarıda kalırsa aynı komutla kaldığı yerden devam eder.

**Neden CLI değil de kütüphane?** Deney belirli hedefleri sabitlemek zorundadır,
oysa `advise` komutu seçiciye bırakır. Bunun için CLI'ya kullanıcının işine
yaramayacak bayraklar eklemek yanlış olurdu.

Kullanım:

    python experiments/run_advice.py --models openai/gpt-oss-120b,qwen/qwen3.8-27b
    python experiments/run_advice.py --models ... --plan   # ne yapılacağını göster
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
from rlens.providers import ProviderError, get_provider, load_env_file  # noqa: E402

DEFAULT_PROJECT = REPO_ROOT / "examples" / "messy_project"
DEFAULT_OUT = REPO_ROOT / "experiments" / "runs"

#: Protokol sabitleri. Sonuçlar görüldükten sonra **değiştirilmez**.
PROTOCOL = {
    "repetitions": 3,
    "temperature": 0.2,
    "top_n": 3,
}


def slug(value: str) -> str:
    """Model adlarındaki `/` ve `:` dizin adı olamaz."""
    return value.replace("/", "_").replace(":", "_")


def prepare_contexts(project: Path, config: Config, top_n: int):
    """Hedefleri seçer ve prompt bağlamlarını kurar.

    Bir kez yapılır ve tüm modeller için aynen kullanılır: modeller arasındaki
    fark, gönderilen prompt farkından değil modelin kendisinden gelmelidir.
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


def output_path(out_dir: Path, model: str, target_name: str, repetition: int) -> Path:
    return out_dir / slug(model) / slug(target_name) / f"rep{repetition}.json"


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
    """Deneyi çalıştırır. Dönen değer: yapılan çağrı sayısı."""
    config = load_config(search_from=project)
    contexts = prepare_contexts(project, config, top_n)

    print(f"project : {project}")
    print(f"targets : {', '.join(t.qualified_name for t, _ in contexts)}")
    print(f"models  : {', '.join(models)}")
    print(f"protocol: n={repetitions}, temperature={config.advise.temperature}")
    print()

    pending: list[tuple[str, int, object, object]] = []
    skipped = 0
    for model in models:
        for repetition in range(1, repetitions + 1):
            for target, context in contexts:
                if output_path(out_dir, model, target.qualified_name, repetition).exists():
                    skipped += 1
                    continue
                pending.append((model, repetition, target, context))

    if skipped:
        print(f"{skipped} run(s) already on disk — skipping them.")
    print(f"{len(pending)} call(s) to make.\n")

    if plan_only:
        for model, repetition, target, _ in pending:
            print(f"  {model}  {target.qualified_name}  rep{repetition}")
        return 0

    if not pending:
        return 0

    load_env_file(project)
    made = 0
    failures: list[str] = []

    for index, (model, repetition, target, context) in enumerate(pending, start=1):
        model_config = replace(config, provider=replace(config.provider, model=model))
        label = f"[{index}/{len(pending)}] {model} {target.qualified_name} rep{repetition}"
        print(label, flush=True)

        try:
            provider = provider_factory(model_config.provider)
            advice, warnings = request_advice(provider, context, model_config)
        except ProviderError as exc:
            # Tek bir modelin çökmesi bütün deneyi durdurmamalı; hata kaydedilir
            # ve diğer kombinasyonlara devam edilir.
            print(f"  FAILED: {exc}")
            failures.append(f"{label}: {exc}")
            continue

        advice.warnings = warnings
        document = AdviceDocument(
            root=str(project.resolve()),
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            rlens_version=__version__,
            provider=model_config.provider.name,
            model=model,
            temperature=model_config.advise.temperature,
            advices=[advice],
        )

        destination = output_path(out_dir, model, target.qualified_name, repetition)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(document.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        made += 1

        suggestions = len(advice.suggestions)
        unlinked = sum(1 for s in advice.suggestions if not s.is_linked)
        note = f"  → {suggestions} suggestion(s)"
        if unlinked:
            note += f", {unlinked} unlinked"
        if advice.repaired:
            note += ", needed repair"
        print(note)

        if index < len(pending) and delay > 0:
            time.sleep(delay)

    print(f"\n{made} run(s) written to {out_dir}")
    if failures:
        print(f"{len(failures)} failure(s):")
        for failure in failures:
            print(f"  {failure}")
    return made


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--models",
        required=True,
        help="Comma-separated model ids, exactly as your provider names them.",
    )
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repetitions", type=int, default=PROTOCOL["repetitions"])
    parser.add_argument("--top-n", type=int, default=PROTOCOL["top_n"])
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds to wait between calls. Free tiers have per-minute limits.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="List the calls that would be made and stop. Sends nothing.",
    )
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
