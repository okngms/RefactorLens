"""DCC elle sayım betiğinin mantığı (`experiments/hardening/dcc_sample.py`).

Elle sayımın sonucu iki şeye dayanır: örneklemin tekrarlanabilir olmasına ve
her şüpheli referansın gerçekten okunup karara bağlanmasına. İkincisini
`judge` zorlar — kararsız referans ya da bayat karar varsa özet üretilmez.
Bu kural kırılırsa kesinlik/duyarlılık sayıları okunmamış referansları doğru
pozitif sayarak şişer; bu yüzden testle korunur.
"""

import ast
import random
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "hardening"))

from dcc_sample import (  # noqa: E402
    EXTERNAL_IMPORT,
    MODULE_ASSIGN,
    MODULE_CLASS,
    PROJECT_IMPORT,
    Reference,
    SampledClass,
    UnreviewedError,
    band_of,
    candidate_name,
    fn_candidates,
    judge,
    local_bindings,
    module_bindings,
    references,
    stratified_pick,
)


def parse(source: str) -> ast.Module:
    return ast.parse(textwrap.dedent(source).strip())


def is_project(name: str) -> bool:
    return name.split(".")[0] in {"myapp", "models"}


class TestSampling:
    @pytest.mark.parametrize(
        ("value", "band"),
        [(0, "low"), (2, "low"), (3, "mid"), (6, "mid"), (7, "high"), (40, "high")],
    )
    def test_bands(self, value, band):
        assert band_of(value) == band

    def test_one_class_per_band_deterministically(self):
        candidates = [("a", 0), ("b", 1), ("c", 4), ("d", 5), ("e", 9)]
        first = stratified_pick(candidates, random.Random(7))
        second = stratified_pick(candidates, random.Random(7))
        assert first == second
        assert [(wanted, got) for _, wanted, got in first] == [
            ("low", "low"),
            ("mid", "mid"),
            ("high", "high"),
        ]

    def test_empty_band_falls_back_without_repeating_a_class(self):
        candidates = [("a", 0), ("b", 1), ("c", 4)]
        picks = stratified_pick(candidates, random.Random(1))
        keys = [key for key, _, _ in picks]
        assert len(keys) == len(set(keys)) == 3
        assert picks[2][1:] == ("high", "mid") or picks[2][1:] == ("high", "low")

    def test_fewer_classes_than_bands(self):
        assert len(stratified_pick([("only", 0)], random.Random(1))) == 1


class TestBindings:
    def test_module_bindings_by_source(self):
        tree = parse(
            """
            from myapp.models import Order
            from urllib3.exceptions import HTTPError
            from .billing import Invoice as Bill
            import models
            class Local: pass
            Alias = Local
            if TYPE_CHECKING:
                from myapp.users import User
            def helper(): pass
            """
        )
        bindings = module_bindings(tree, is_project)
        assert bindings["Order"][0][0] == PROJECT_IMPORT
        assert bindings["HTTPError"][0][0] == EXTERNAL_IMPORT
        assert bindings["Bill"][0][0] == PROJECT_IMPORT
        assert bindings["models"][0][0] == PROJECT_IMPORT
        assert bindings["Local"][0][0] == MODULE_CLASS
        assert bindings["Alias"][0][0] == MODULE_ASSIGN
        assert bindings["User"][0][0] == PROJECT_IMPORT

    def test_local_bindings(self):
        node = parse(
            """
            class C:
                def m(self, Order):
                    for Item in x: pass
                    try: pass
                    except E as Failure: pass
                    Result = 1
            """
        ).body[0]
        assert {"Order", "Item", "Failure", "Result"} <= local_bindings(node)


class TestHints:
    def ref(self, forms, binding, local=False):
        return Reference("X", forms, binding, local)

    def test_project_import_is_likely_tp(self):
        assert self.ref(["name"], [(PROJECT_IMPORT, "")]).hint == "likely_tp"

    def test_external_only_is_likely_fp(self):
        assert self.ref(["name"], [(EXTERNAL_IMPORT, "")]).hint == "likely_fp_external"

    def test_local_name_is_likely_fp(self):
        assert self.ref(["name"], [], local=True).hint == "likely_fp_local_name"

    def test_attribute_only_needs_reading(self):
        assert self.ref(["attr:types"], [(PROJECT_IMPORT, "")]).hint == "check_attribute"

    def test_unbound_needs_reading(self):
        assert self.ref(["name"], []).hint == "check_unbound"

    def test_references_record_forms(self):
        tree = parse(
            """
            from myapp.models import Order as O
            class Service:
                def run(self, x: "Invoice") -> None:
                    return O(), models.Customer
            """
        )
        node = tree.body[1]
        names = frozenset({"Order", "Invoice", "Customer"})
        forms = {r.name: r.forms for r in references(node, tree, names, is_project)}
        assert forms == {"Order": ["alias:O"], "Invoice": ["string"], "Customer": ["attr:models"]}

    def test_references_exclude_own_nested_classes(self):
        """Çalışma kâğıdı `dcc()` ile aynı sayıyı vermeli (şema 3, K3)."""
        tree = parse(
            """
            class Loader:
                class Collections:
                    pass
                def run(self):
                    class Model:
                        pass
                    return self.Collections(), Model(), Order()
            """
        )
        node = tree.body[0]
        names = frozenset({"Collections", "Model", "Order"})
        assert [r.name for r in references(node, tree, names, is_project)] == ["Order"]


class TestFalseNegativeCandidates:
    def test_string_outside_annotations_type_alias_and_same_name(self):
        tree = parse(
            """
            OrderLike = Union[Order, Draft]
            class Service:
                def run(self, value: OrderLike):
                    return cast("Invoice", value), Customer
            """
        )
        node = tree.body[1]
        names = frozenset({"Order", "Draft", "Invoice", "Customer"})
        candidates = fn_candidates(node, tree, names, {"Customer"}, {"Customer": 2})
        assert candidates == [
            "same_name:Customerx2",
            "string:Invoice",
            "via_alias:OrderLike->Draft",
            "via_alias:OrderLike->Order",
        ]

    @pytest.mark.parametrize(
        ("candidate", "name"),
        [
            ("via_alias:A->Order", "Order"),
            ("same_name:HTTPBasex2", "HTTPBase"),
            ("string:Order", "Order"),
        ],
    )
    def test_candidate_name(self, candidate, name):
        assert candidate_name(candidate) == name


def sampled(key="p:m:C", refs=(), candidates=()):
    return SampledClass(key, "low", "low", "m.py", 1, 10, list(refs), list(candidates))


class TestJudge:
    def test_likely_tp_without_verdict_is_accepted(self):
        item = sampled(refs=[Reference("Order", ["name"], [(PROJECT_IMPORT, "")], False)])
        rows, summary = judge([item], {})
        assert rows[0]["verdict"] == "tp"
        assert summary["precision"] == 1.0

    def test_suspicious_reference_without_verdict_is_refused(self):
        item = sampled(refs=[Reference("Response", ["name"], [(EXTERNAL_IMPORT, "")], False)])
        with pytest.raises(UnreviewedError, match="Response"):
            judge([item], {})

    def test_unreviewed_fn_candidate_is_refused(self):
        item = sampled(candidates=["via_alias:A->Order"])
        with pytest.raises(UnreviewedError, match="FN candidate"):
            judge([item], {})

    def test_stale_verdicts_are_refused(self):
        item = sampled()
        with pytest.raises(UnreviewedError, match="without a counted reference"):
            judge([item], {"references": {"p:m:C": {"Gone": {"verdict": "fp", "category": "x"}}}})
        with pytest.raises(UnreviewedError, match="not in the sample"):
            judge([item], {"false_negatives": {"other:m:D": []}})

    def test_summary_arithmetic(self):
        refs = [
            Reference("A", ["name"], [(PROJECT_IMPORT, "")], False),
            Reference("B", ["name"], [(PROJECT_IMPORT, "")], False),
            Reference("C", ["name"], [(EXTERNAL_IMPORT, "")], False),
        ]
        item = sampled(refs=refs, candidates=["via_alias:T->D", "same_name:Ax2"])
        verdicts = {
            "references": {"p:m:C": {"C": {"verdict": "fp", "category": "external_same_name"}}},
            "false_negatives": {"p:m:C": [{"name": "D", "category": "type_alias"}]},
            "rejected_candidates": {"p:m:C": {"same_name:Ax2": "only one A used"}},
        }
        rows, summary = judge([item, sampled("p:m:Exact")], verdicts)
        assert (
            summary["true_positives"],
            summary["false_positives"],
            summary["false_negatives"],
        ) == (2, 1, 1)
        assert summary["precision"] == round(2 / 3, 4)
        assert summary["recall"] == round(2 / 3, 4)
        assert summary["classes_exact"] == 1
        assert summary["per_class"]["p:m:C"] == {"band": "low", "measured": 3, "true": 3}
