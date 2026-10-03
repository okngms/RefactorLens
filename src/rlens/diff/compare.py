"""İki ref'i tarayıp karşılaştırmak (`docs/02` §8).

İki taraf da **bugünkü** config ile taranır: aynı kural, iki kod. Taranan
yol depo köküne göre aynıdır. Fark `verify` ile aynı hesaplanır (metrik
deltası, ihlal ve koku kümeleri, Goodhart); ek olarak değişen Python
dosyalarında refactoring türü tespit edilir ve ratchet bulguları çıkarılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rlens.analysis.refactoring_types import Detection, detect
from rlens.analysis.scanner import scan_project
from rlens.apply.worktree import repository_root
from rlens.config import Config
from rlens.diff.baseline import findings, load_baseline
from rlens.diff.git_refs import changed_python_files, checkout, resolve
from rlens.verify import goodhart as goodhart_module
from rlens.verify.diff import REGRESSED, ProjectDelta, diff_reports

DIFF_SCHEMA_VERSION = 1


@dataclass
class DiffResult:
    base: str
    head: str
    base_commit: str
    head_commit: str
    delta: ProjectDelta
    goodhart: object
    refactorings: list[Detection] = field(default_factory=list)
    new_findings: list[str] = field(default_factory=list)
    fixed_findings: list[str] = field(default_factory=list)
    accepted_from: str = "base"
    """`baseline` ya da `base`: yeni bulgular neye göre yeni."""

    @property
    def regressed(self) -> bool:
        return any(entity.summarise() == REGRESSED for entity in self.delta.entities)

    def to_dict(self) -> dict:
        return {
            "schema_version": DIFF_SCHEMA_VERSION,
            "base": self.base,
            "head": self.head,
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "delta": self.delta.to_dict(),
            "goodhart": self.goodhart.to_dict(),
            "refactorings": [d.to_dict() for d in self.refactorings],
            "accepted_from": self.accepted_from,
            "new_findings": list(self.new_findings),
            "fixed_findings": list(self.fixed_findings),
        }


def _sources(base: Path, names: list[str]) -> dict[str, str]:
    sources = {}
    for name in names:
        path = base / name
        if path.is_file():
            sources[name] = path.read_text(encoding="utf-8", errors="replace")
    return sources


def run_diff(
    path: Path, base: str, head: str, config: Config, *, baseline: Path | None = None
) -> DiffResult:
    root = repository_root(path)
    prefix = Path(path).resolve().relative_to(root)
    changed = [
        name
        for name in changed_python_files(root, base, head)
        if prefix == Path(".") or Path(name).is_relative_to(prefix)
    ]
    with checkout(root, base) as old_tree, checkout(root, head) as new_tree:
        before = scan_project(old_tree / prefix, config).to_dict()
        after = scan_project(new_tree / prefix, config).to_dict()
        refactorings = detect(_sources(old_tree, changed), _sources(new_tree, changed))

    delta = diff_reports(before, after)
    accepted = load_baseline(baseline) if baseline else findings(before, config)
    current = findings(after, config)
    return DiffResult(
        base=base,
        head=head,
        base_commit=resolve(root, base),
        head_commit=resolve(root, head),
        delta=delta,
        goodhart=goodhart_module.detect(before, after, delta.entities),
        refactorings=refactorings,
        new_findings=sorted(current - accepted),
        fixed_findings=sorted(findings(before, config) - current),
        accepted_from="baseline" if baseline else "base",
    )
