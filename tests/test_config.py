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
        with pytest.raises(ConfigError, match="Bilinmeyen config"):
            load_config(search_from=tmp_path)

    def test_unknown_key_rejected(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_nn: 3\n")
        with pytest.raises(ConfigError, match="bilinmeyen anahtar"):
            load_config(search_from=tmp_path)

    def test_unknown_threshold_key_rejected(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  dcc: {warn: 3, criticl: 9}\n")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)

    def test_unknown_provider_rejected(self, tmp_path):
        write_config(tmp_path, "provider:\n  name: openai\n")
        with pytest.raises(ConfigError, match="Bilinmeyen sağlayıcı"):
            load_config(search_from=tmp_path)

    def test_critical_must_exceed_warn(self, tmp_path):
        write_config(tmp_path, "thresholds:\n  lcom4: {warn: 5, critical: 2}\n")
        with pytest.raises(ConfigError, match="critical"):
            load_config(search_from=tmp_path)

    def test_cam_coverage_out_of_range(self, tmp_path):
        write_config(tmp_path, "metrics:\n  cam_min_annotation_coverage: 1.4\n")
        with pytest.raises(ConfigError, match="0.0–1.0"):
            load_config(search_from=tmp_path)

    def test_top_n_must_be_positive(self, tmp_path):
        write_config(tmp_path, "advise:\n  top_n: 0\n")
        with pytest.raises(ConfigError):
            load_config(search_from=tmp_path)

    def test_include_must_be_list_of_strings(self, tmp_path):
        write_config(tmp_path, "scan:\n  include: 'src/'\n")
        with pytest.raises(ConfigError, match="liste"):
            load_config(search_from=tmp_path)

    def test_invalid_yaml_reports_path(self, tmp_path):
        write_config(tmp_path, "advise: [unclosed\n")
        with pytest.raises(ConfigError, match="YAML"):
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
