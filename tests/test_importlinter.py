"""import-linter sözleşmelerinden katman beyanı okuma testleri."""

import pytest

from rlens.config import load_config
from rlens.integrations.importlinter import (
    apply_to_arch,
    layers_from_contracts,
    read_import_linter,
    scheme_from,
)

PYPROJECT = """
[tool.importlinter]
root_package = "myapp"

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["myapp.api", "myapp.services", "myapp.domain"]
"""

INI = """
[importlinter]
root_package = myapp

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    myapp.api
    myapp.services
    myapp.domain
"""


def write(tmp_path, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")
    return tmp_path


class TestDiscovery:
    def test_nothing_found_is_not_an_error(self, tmp_path):
        """Çoğu proje import-linter kullanmaz."""
        config = read_import_linter(tmp_path)
        assert config.found is False
        assert "no import-linter" in config.describe()

    def test_pyproject(self, tmp_path):
        config = read_import_linter(write(tmp_path, "pyproject.toml", PYPROJECT))
        assert config.found is True
        assert config.contracts[0].name == "Layered architecture"

    def test_importlinter_ini(self, tmp_path):
        config = read_import_linter(write(tmp_path, ".importlinter", INI))
        assert config.found is True
        assert config.contracts[0].layers == ("myapp.api", "myapp.services", "myapp.domain")

    def test_setup_cfg(self, tmp_path):
        config = read_import_linter(write(tmp_path, "setup.cfg", INI))
        assert config.found is True

    def test_pyproject_without_the_section_is_skipped(self, tmp_path):
        write(tmp_path, "pyproject.toml", '[project]\nname = "x"\n')
        assert read_import_linter(tmp_path).found is False

    def test_malformed_toml_does_not_raise(self, tmp_path):
        write(tmp_path, "pyproject.toml", "[[[ not toml")
        assert read_import_linter(tmp_path).found is False

    def test_describe_names_the_file(self, tmp_path):
        config = read_import_linter(write(tmp_path, "pyproject.toml", PYPROJECT))
        assert "pyproject.toml" in config.describe()


class TestContractSelection:
    def test_non_layers_contracts_are_skipped_with_a_reason(self, tmp_path):
        """`forbidden` ve `independence` katman sırası vermez."""
        write(
            tmp_path,
            "pyproject.toml",
            PYPROJECT + '\n[[tool.importlinter.contracts]]\nname = "Indep"\ntype = "independence"\n'
            'modules = ["myapp.a"]\n',
        )
        config = read_import_linter(tmp_path)
        assert len(config.contracts) == 1
        assert any("independence" in reason for reason in config.skipped)

    def test_single_layer_contract_is_useless(self, tmp_path):
        write(
            tmp_path,
            "pyproject.toml",
            "[tool.importlinter]\n[[tool.importlinter.contracts]]\n"
            'name = "One"\ntype = "layers"\nlayers = ["myapp.only"]\n',
        )
        config = read_import_linter(tmp_path)
        assert config.contracts == []
        assert any("fewer than two" in reason for reason in config.skipped)


class TestPrefixes:
    def test_dots_become_path_separators(self, tmp_path):
        config = read_import_linter(write(tmp_path, "pyproject.toml", PYPROJECT))
        assert layers_from_contracts(config)["domain"] == ("myapp/domain/",)

    def test_containers_qualify_the_layers(self, tmp_path):
        write(
            tmp_path,
            "pyproject.toml",
            "[tool.importlinter]\n[[tool.importlinter.contracts]]\n"
            'name = "C"\ntype = "layers"\n'
            'containers = ["myapp", "other"]\nlayers = ["api", "domain"]\n',
        )
        prefixes = layers_from_contracts(read_import_linter(tmp_path))
        assert prefixes["api"] == ("myapp/api/", "other/api/")


class TestSchemeDerivation:
    """import-linter semantiği: üst katman alttakileri import edebilir."""

    @pytest.fixture
    def contract(self, tmp_path):
        return read_import_linter(write(tmp_path, "pyproject.toml", PYPROJECT)).contracts[0]

    def test_layer_names_are_shortened(self, contract):
        layers, _ = scheme_from(contract)
        assert layers == ("api", "services", "domain")

    def test_downward_imports_are_allowed(self, contract):
        _, allowed = scheme_from(contract)
        assert "domain" in allowed["api"]
        assert "services" in allowed["api"]

    def test_upward_imports_are_forbidden(self, contract):
        _, allowed = scheme_from(contract)
        assert allowed["domain"] == ()


class TestApplyToArch:
    def test_declaration_in_rlens_yaml_wins(self, tmp_path):
        """Kullanıcının açık tercihi bir dosya okumasıyla ezilmez."""
        write(tmp_path, "pyproject.toml", PYPROJECT)
        (tmp_path / "rlens.yaml").write_text(
            'arch:\n  layers:\n    domain: ["src/domain/"]\n', encoding="utf-8"
        )
        config = load_config(search_from=tmp_path)
        arch, notes = apply_to_arch(config.arch, read_import_linter(tmp_path))
        assert arch.declared == {"domain": ("src/domain/",)}
        assert any("takes precedence" in note for note in notes)

    def test_contracts_are_used_when_nothing_is_declared(self, tmp_path):
        write(tmp_path, "pyproject.toml", PYPROJECT)
        config = load_config(search_from=tmp_path)
        arch, notes = apply_to_arch(config.arch, read_import_linter(tmp_path))
        assert arch.scheme.layers == ("api", "services", "domain")
        assert arch.has_declaration is True
        assert any("layers read from" in note for note in notes)

    def test_skip_is_allowed_in_a_derived_scheme(self, tmp_path):
        """import-linter yalnızca yukarı doğru importu yasaklar."""
        write(tmp_path, "pyproject.toml", PYPROJECT)
        config = load_config(search_from=tmp_path)
        arch, _ = apply_to_arch(config.arch, read_import_linter(tmp_path))
        assert arch.scheme.allow_skip is True

    def test_nothing_found_leaves_arch_untouched(self, tmp_path):
        config = load_config(search_from=tmp_path)
        arch, notes = apply_to_arch(config.arch, read_import_linter(tmp_path))
        assert arch is config.arch
        assert notes == []

    def test_extra_layers_contracts_are_reported(self, tmp_path):
        write(
            tmp_path,
            "pyproject.toml",
            PYPROJECT + '\n[[tool.importlinter.contracts]]\nname = "Second"\ntype = "layers"\n'
            'layers = ["myapp.x", "myapp.y"]\n',
        )
        config = load_config(search_from=tmp_path)
        _, notes = apply_to_arch(config.arch, read_import_linter(tmp_path))
        assert any("further layers contract" in note for note in notes)
