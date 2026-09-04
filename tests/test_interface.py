"""Public arayüz kümesi testleri."""

import ast

import pytest

from rlens.analysis.interface import (
    PublicInterface,
    diff_interfaces,
    is_public,
    public_interface,
)


def parse(source: str) -> ast.ClassDef:
    return ast.parse(source.strip()).body[0]


class TestIsPublic:
    @pytest.mark.parametrize("name", ["value", "compute", "a"])
    def test_plain_names_are_public(self, name):
        assert is_public(name) is True

    @pytest.mark.parametrize("name", ["_value", "__value", "__init__", "_"])
    def test_underscored_names_are_not(self, name):
        assert is_public(name) is False


class TestMethods:
    def test_public_methods_are_collected(self):
        node = parse("class C:\n    def a(self): pass\n    def b(self): pass")
        assert public_interface(node).methods == ("a", "b")

    def test_dunder_and_private_are_excluded(self):
        node = parse(
            "class C:\n"
            "    def __init__(self): pass\n"
            "    def _hidden(self): pass\n"
            "    def shown(self): pass"
        )
        assert public_interface(node).methods == ("shown",)

    def test_nested_class_methods_do_not_leak_in(self):
        node = parse(
            "class Outer:\n"
            "    class Inner:\n        def inner_method(self): pass\n"
            "    def outer_method(self): pass"
        )
        assert public_interface(node).methods == ("outer_method",)


class TestAttributes:
    def test_class_level_assignment(self):
        assert public_interface(parse("class C:\n    x = 1")).attributes == ("x",)

    def test_class_level_annotation(self):
        assert public_interface(parse("class C:\n    x: int")).attributes == ("x",)

    def test_self_assignment_in_any_method(self):
        node = parse(
            "class C:\n"
            "    def __init__(self):\n        self.a = 1\n"
            "    def later(self):\n        self.b = 2"
        )
        assert public_interface(node).attributes == ("a", "b")

    def test_private_attributes_are_excluded(self):
        node = parse("class C:\n    def __init__(self):\n        self._a = 1\n        self.b = 2")
        assert public_interface(node).attributes == ("b",)

    def test_read_only_access_is_not_an_attribute(self):
        node = parse("class C:\n    def m(self):\n        return self.external")
        assert public_interface(node).attributes == ()


class TestAccessors:
    def test_single_return_of_an_attribute(self):
        node = parse("class C:\n    def name(self):\n        return self._name")
        assert public_interface(node).accessors == ("name",)

    def test_docstring_is_allowed(self):
        """Belgelenmiş bir erişimci hâlâ erişimcidir."""
        node = parse(
            'class C:\n    def name(self):\n        """The name."""\n        return self._n'
        )
        assert public_interface(node).accessors == ("name",)

    def test_computation_is_not_an_accessor(self):
        node = parse("class C:\n    def total(self):\n        return self._a + self._b")
        assert public_interface(node).accessors == ()

    def test_branching_is_not_an_accessor(self):
        node = parse(
            "class C:\n    def v(self):\n"
            "        if self._a:\n            return 1\n"
            "        return self._b"
        )
        assert public_interface(node).accessors == ()

    def test_returning_another_object_is_not_an_accessor(self):
        node = parse("class C:\n    def v(self, other):\n        return other.value")
        assert public_interface(node).accessors == ()

    def test_ratio(self):
        node = parse(
            "class C:\n"
            "    def a(self):\n        return self._a\n"
            "    def b(self):\n        return self._b\n"
            "    def c(self):\n        return self._a + self._b"
        )
        assert public_interface(node).accessor_ratio == 0.6667  # 4 haneye yuvarlanır

    def test_ratio_is_none_without_methods(self):
        """Sıfır yanıltıcı olurdu: sorulacak metot yok."""
        assert public_interface(parse("class C:\n    x = 1")).accessor_ratio is None


class TestSizeAndNames:
    def test_names_merge_methods_and_attributes(self):
        node = parse("class C:\n    x = 1\n    def m(self): pass")
        interface = public_interface(node)
        assert interface.names == {"x", "m"}
        assert interface.size == 2

    def test_serialisation(self):
        payload = public_interface(parse("class C:\n    def m(self): pass")).to_dict()
        assert payload["methods"] == ["m"]
        assert payload["size"] == 1


class TestDiff:
    def test_removed_members_are_detected(self):
        """v1'de bir model tüm arayüzü silerek metrikleri 'iyileştirdi'."""
        before = PublicInterface(methods=("a", "b", "c"))
        after = PublicInterface(methods=("a",))
        delta = diff_interfaces(before, after)
        assert delta.removed == ("b", "c")
        assert delta.shrank is True

    def test_added_members(self):
        delta = diff_interfaces(
            PublicInterface(methods=("a",)), PublicInterface(methods=("a", "b"))
        )
        assert delta.added == ("b",)
        assert delta.shrank is False

    def test_unchanged_interface(self):
        interface = PublicInterface(methods=("a",), attributes=("x",))
        delta = diff_interfaces(interface, interface)
        assert delta.removed == () and delta.added == ()
        assert len(delta.kept) == 2

    def test_serialisation(self):
        delta = diff_interfaces(
            PublicInterface(methods=("a", "b")), PublicInterface(methods=("a",))
        )
        assert delta.to_dict()["removed"] == ["b"]
