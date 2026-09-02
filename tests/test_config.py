"""config.py testleri."""

import pytest

from rlens.config import (
    DEFAULTS,
    ConfigError,
    Threshold,
    find_config_file,
    load_config,
)


def write_config(tmp_path, text):
    path = tmp_path / "rlens.yaml"
    path.write_text(text, encoding="utf-8")
    return path


class TestDefaults:
    def test_missing_config_uses_defaults(self, tmp_path):
        config = load_config(search_from=tmp_path)
        assert config.loaded_from_file is False
        assert config.provider.name == DEFAULTS["provider"]["name"]
        assert config.advise.top_n == 3
        assert config.metrics.cam_min_annotation_coverage == 0.7

    def test_model_is_not_hardcoded(self, tmp_path):
        """Model adı koda gömülmez; varsayılan boştur."""
        assert load_config(search_from=tmp_path).provider.model is None

    def test_explicit_missing_path_raises(self, tmp_path):
        with pytest.raises(ConfigError):
            load_config(tmp_path / "yok.yaml")


class TestMerging:
    def test_partial_override_keeps_other_defaults(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_n: 5\n")
        config = load_config(search_from=tmp_path)
        assert config.advise.top_n == 5
        assert config.advise.max_context_tokens == 12000

    def test_threshold_override_keeps_other_thresholds(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  dcc: {warn: 3}\n")
        config = load_config(search_from=tmp_path)
        assert config.thresholds["dcc"].warn == 3
        assert config.thresholds["lcom4"].warn == 2

    def test_empty_file_is_valid(self, tmp_path):
        write_config(tmp_path, "")
        assert load_config(search_from=tmp_path).advise.top_n == 3

    def test_config_is_found_from_subdirectory(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_n: 7\n")
        nested = tmp_path / "src" / "pkg"
        nested.mkdir(parents=True)
        assert load_config(search_from=nested).advise.top_n == 7

    def test_find_config_file_returns_none_when_absent(self, tmp_path):
        assert find_config_file(tmp_path) is None


class TestValidation:
    """Sessizce yanlış çalışmaktansa gürültülü şekilde durmak."""

    def test_unknown_section_rejected(self, tmp_path):
        write_config(tmp_path, "provierd:\n  name: groq\n")
        with pytest.raises(ConfigError, match="Unknown config section"):
            load_config(search_from=tmp_path)

    def test_unknown_key_rejected(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_nn: 3\n")
        with pytest.raises(ConfigError, match="Unknown key under"):
            load_config(search_from=tmp_path)

    def test_unknown_threshold_key_rejected(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  dcc: {warn: 3, criticl: 9}\n")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)

    def test_unknown_provider_rejected(self, tmp_path):
        write_config(tmp_path, "provider:\n  name: openai\n")
        with pytest.raises(ConfigError, match="Unknown provider"):
            load_config(search_from=tmp_path)

    def test_critical_must_exceed_warn(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  lcom4: {warn: 5, critical: 2}\n")
        with pytest.raises(ConfigError, match="critical"):
            load_config(search_from=tmp_path)

    def test_cam_coverage_out_of_range(self, tmp_path):
        write_config(tmp_path, "metrics:\n  cam_min_annotation_coverage: 1.4\n")
        with pytest.raises(ConfigError, match="must be between"):
            load_config(search_from=tmp_path)

    def test_top_n_must_be_positive(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_n: 0\n")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)

    def test_include_must_be_list_of_strings(self, tmp_path):
        write_config(tmp_path, "scan:\n  include: 'src/'\n")
        with pytest.raises(ConfigError, match="must be a list"):
            load_config(search_from=tmp_path)

    def test_invalid_yaml_reports_path(self, tmp_path):
        write_config(tmp_path, "advise: [unclosed\n")
        with pytest.raises(ConfigError, match="not valid YAML"):
            load_config(search_from=tmp_path)


class TestThreshold:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(1, None), (2, "warn"), (3, "warn"), (4, "critical"), (10, "critical")],
    )
    def test_levels(self, value, expected):
        assert Threshold(warn=2, critical=4).level(value) == expected

    def test_none_value_never_violates(self):
        """Hesaplanamayan metrik (CAM null) ihlal üretmez."""
        assert Threshold(warn=2, critical=4).level(None) is None

    def test_warn_only_threshold(self):
        threshold = Threshold(warn=5)
        assert threshold.level(9) == "warn"
        assert threshold.level(4) is None


class TestProviderConfig:
    def test_ollama_is_local(self, tmp_path):
        write_config(tmp_path, "provider:\n  name: ollama\n")
        assert load_config(search_from=tmp_path).provider.is_local is True

    def test_groq_is_not_local(self, tmp_path):
        assert load_config(search_from=tmp_path).provider.is_local is False


class TestScanDefaults:
    """Varsayılan include'un davranışı — dogfooding sırasında bulunan tuzak."""

    def test_include_defaults_to_everything(self, tmp_path):
        """`src/` varsayılanı `rlens scan src/pkg` komutunu sessizce boş bırakırdı."""
        assert load_config(search_from=tmp_path).scan.include == (".",)

    def test_tests_are_excluded_by_default(self, tmp_path):
        assert "tests/" in load_config(search_from=tmp_path).scan.exclude


class TestArchScheme:
    """Katman şeması: adlar üç yerde geçer, hepsi birbirine karşı doğrulanır."""

    def test_defaults(self, tmp_path):
        arch = load_config(search_from=tmp_path).arch
        assert arch.enabled is True
        assert arch.scheme.layers == (
            "presentation",
            "application",
            "domain",
            "infrastructure",
        )
        assert arch.min_confidence == 0.5

    def test_default_permissions(self, tmp_path):
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert scheme.may_import("application", "domain") is True
        assert scheme.may_import("domain", "infrastructure") is False
        assert scheme.may_import("presentation", "infrastructure") is False

    def test_same_layer_is_always_allowed(self, tmp_path):
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert scheme.may_import("domain", "domain") is True

    def test_depth_follows_declaration_order(self, tmp_path):
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert scheme.depth("presentation") < scheme.depth("domain")
        assert scheme.depth("nonexistent") is None

    def test_redefining_layers_replaces_permissions(self, tmp_path):
        """Katman kümesi değişirse varsayılan izinler taşınmaz."""
        write_config(
            tmp_path,
            "arch:\n  scheme:\n    layers: [ui, core]\n    allowed:\n      ui: [core]\n",
        )
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert set(scheme.allowed) == {"ui"}
        assert "presentation" not in scheme.allowed

    def test_custom_scheme(self, tmp_path):
        write_config(
            tmp_path,
            "arch:\n"
            "  scheme:\n"
            "    layers: [ui, core]\n"
            "    allowed:\n"
            "      ui: [core]\n"
            "      core: []\n",
        )
        scheme = load_config(search_from=tmp_path).arch.scheme
        assert scheme.layers == ("ui", "core")
        assert scheme.may_import("ui", "core") is True

    def test_unknown_layer_in_allowed_is_rejected(self, tmp_path):
        write_config(
            tmp_path,
            "arch:\n  scheme:\n    layers: [ui, core]\n    allowed:\n      ui: [database]\n",
        )
        with pytest.raises(ConfigError, match="unknown layer"):
            load_config(search_from=tmp_path)

    def test_unknown_source_layer_is_rejected(self, tmp_path):
        write_config(
            tmp_path,
            "arch:\n  scheme:\n    layers: [ui, core]\n    allowed:\n      web: [core]\n",
        )
        with pytest.raises(ConfigError, match="not in arch.scheme.layers"):
            load_config(search_from=tmp_path)

    def test_repeated_layer_name_is_rejected(self, tmp_path):
        write_config(tmp_path, "arch:\n  scheme:\n    layers: [ui, ui]\n")
        with pytest.raises(ConfigError, match="must not repeat"):
            load_config(search_from=tmp_path)

    def test_declared_layer_must_exist_in_scheme(self, tmp_path):
        write_config(tmp_path, "arch:\n  layers:\n    persistence: ['src/db/']\n")
        with pytest.raises(ConfigError, match="not in arch.scheme.layers"):
            load_config(search_from=tmp_path)

    def test_declaration_is_read(self, tmp_path):
        write_config(tmp_path, "arch:\n  layers:\n    domain: ['src/domain/']\n")
        arch = load_config(search_from=tmp_path).arch
        assert arch.has_declaration is True
        assert arch.declared["domain"] == ("src/domain/",)

    def test_no_declaration_by_default(self, tmp_path):
        assert load_config(search_from=tmp_path).arch.has_declaration is False

    def test_min_confidence_range(self, tmp_path):
        write_config(tmp_path, "arch:\n  min_confidence: 1.5\n")
        with pytest.raises(ConfigError, match="between"):
            load_config(search_from=tmp_path)

    def test_unknown_arch_key(self, tmp_path):
        write_config(tmp_path, "arch:\n  enabledd: true\n")
        with pytest.raises(ConfigError, match="Unknown key under `arch`"):
            load_config(search_from=tmp_path)

    def test_unknown_scheme_key(self, tmp_path):
        write_config(tmp_path, "arch:\n  scheme:\n    layerz: [a]\n")
        with pytest.raises(ConfigError, match="arch.scheme"):
            load_config(search_from=tmp_path)


class TestLayerThresholds:
    """Aynı DCC değeri farklı katmanlarda farklı anlama gelir."""

    def test_general_threshold_when_no_override(self, tmp_path):
        config = load_config(search_from=tmp_path)
        assert config.threshold_for("dcc").warn == 7

    def test_layer_override_applies(self, tmp_path):
        write_config(
            tmp_path,
            "thresholds:\n  by_layer:\n    domain: {dcc: {warn: 4}}\n"
            "    application: {dcc: {warn: 12}}\n",
        )
        config = load_config(search_from=tmp_path)
        assert config.threshold_for("dcc", "domain").warn == 4
        assert config.threshold_for("dcc", "application").warn == 12

    def test_unoverridden_metric_falls_back(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  by_layer:\n    domain: {dcc: {warn: 4}}\n")
        config = load_config(search_from=tmp_path)
        assert config.threshold_for("lcom4", "domain").warn == 2

    def test_unknown_layer_uses_the_general_threshold(self, tmp_path):
        """Katman çıkarılamadıysa tahmin zorlanmaz, genel eşik kullanılır."""
        write_config(tmp_path, "thresholds:\n  by_layer:\n    domain: {dcc: {warn: 4}}\n")
        config = load_config(search_from=tmp_path)
        assert config.threshold_for("dcc", "unknown").warn == 7
        assert config.threshold_for("dcc", None).warn == 7

    def test_layer_must_exist_in_scheme(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  by_layer:\n    persistence: {dcc: {warn: 4}}\n")
        with pytest.raises(ConfigError, match="unknown layer"):
            load_config(search_from=tmp_path)

    def test_bad_threshold_shape_is_rejected(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  by_layer:\n    domain: {dcc: {warnn: 4}}\n")
        with pytest.raises(ConfigError, match="by_layer"):
            load_config(search_from=tmp_path)

    def test_by_layer_is_not_mistaken_for_a_metric(self, tmp_path):
        """`by_layer` bir metrik adı değil; genel eşik sözlüğüne girmemeli."""
        write_config(tmp_path, "thresholds:\n  by_layer:\n    domain: {dcc: {warn: 4}}\n")
        assert "by_layer" not in load_config(search_from=tmp_path).thresholds


class TestSmellRules:
    def test_defaults_match_the_documented_rule(self, tmp_path):
        smells = load_config(search_from=tmp_path).smells
        assert (smells.god_class_nom, smells.god_class_wmc, smells.god_class_lcom4) == (20, 50, 3)
        assert smells.data_class_max_nom == 5
        assert smells.data_class_accessor_ratio == 0.7

    def test_rules_are_configurable(self, tmp_path):
        write_config(tmp_path, "smells:\n  god_class: {nom: 15}\n")
        assert load_config(search_from=tmp_path).smells.god_class_nom == 15

    def test_unknown_rule_is_rejected(self, tmp_path):
        write_config(tmp_path, "smells:\n  shotgun_surgery: {n: 3}\n")
        with pytest.raises(ConfigError, match="Unknown smell rule"):
            load_config(search_from=tmp_path)

    def test_unknown_key_inside_a_rule_is_rejected(self, tmp_path):
        write_config(tmp_path, "smells:\n  god_class: {noms: 20}\n")
        with pytest.raises(ConfigError, match="smells.god_class"):
            load_config(search_from=tmp_path)

    def test_ratio_range_is_validated(self, tmp_path):
        write_config(tmp_path, "smells:\n  data_class: {min_dam: 2.0}\n")
        with pytest.raises(ConfigError, match="between"):
            load_config(search_from=tmp_path)


class TestBudgetAndCache:
    def test_defaults(self, tmp_path):
        config = load_config(search_from=tmp_path)
        assert config.budget.max_calls_per_run == 10
        assert config.cache.enabled is True
        assert config.cache.directory == ".rlens-cache/"

    def test_budget_must_be_positive(self, tmp_path):
        write_config(tmp_path, "budget:\n  max_calls_per_run: 0\n")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)

    def test_token_ceiling_has_a_floor(self, tmp_path):
        """Anlamsızca küçük bir tavan her prompt'u reddederdi."""
        write_config(tmp_path, "budget:\n  max_tokens_per_call: 10\n")
        with pytest.raises(ConfigError, match="at least"):
            load_config(search_from=tmp_path)

    def test_cache_can_be_disabled(self, tmp_path):
        write_config(tmp_path, "cache:\n  enabled: false\n")
        assert load_config(search_from=tmp_path).cache.enabled is False

    def test_cache_enabled_must_be_boolean(self, tmp_path):
        write_config(tmp_path, "cache:\n  enabled: sometimes\n")
        with pytest.raises(ConfigError, match="true or false"):
            load_config(search_from=tmp_path)


class TestVerifySettings:
    def test_suspicious_is_a_regression_by_default(self, tmp_path):
        assert load_config(search_from=tmp_path).verify.treat_suspicious_as_regression is True

    def test_can_be_turned_off(self, tmp_path):
        write_config(tmp_path, "verify:\n  treat_suspicious_as_regression: false\n")
        assert load_config(search_from=tmp_path).verify.treat_suspicious_as_regression is False


class TestBackwardCompatibility:
    def test_a_v1_config_still_loads(self, tmp_path):
        """Eski config dosyaları çalışmaya devam etmeli."""
        write_config(
            tmp_path,
            "scan:\n  include: ['src/']\n  exclude: ['tests/']\n"
            "advise:\n  top_n: 2\n"
            "thresholds:\n  lcom4: {warn: 3}\n",
        )
        config = load_config(search_from=tmp_path)
        assert config.advise.top_n == 2
        assert config.thresholds["lcom4"].warn == 3
        assert config.arch is not None
