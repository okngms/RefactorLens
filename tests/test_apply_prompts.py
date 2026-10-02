"""`apply` patch prompt'u ve yanıt ayrıştırıcısı (v2.4 Aşama 1).

Sabitlenenler:

* Prompt önerinin metnini taşır, modelin kendi tahminini (`expected_effect`)
  **taşımaz**: patch tahmini tutturmak için yazılırsa ölçülen tahmin doğruluğu
  şişer (Goodhart).
* Ham eşik sayıları ve ölçümler prompt'a hiç girmez (invariant).
* İzin verilen dosyalar prompt'ta adıyla yazılır; yanıt tek bir ```diff bloğu
  olmalıdır, yoksa reddedilir ve onarım prompt'u reddin nedenini taşır.
"""

from __future__ import annotations

import pytest

from rlens.apply.prompts import (
    SYSTEM_INSTRUCTION,
    PatchFormatError,
    build_patch_prompt,
    build_repair_prompt,
    parse_patch,
)

SUGGESTION = {
    "title": "Extract the audit log",
    "sketch": "Move record_audit and audit_trail into a new AuditLog class.",
    "expected_effect": [
        {"metric": "LCOM4", "direction": "down", "confidence": 0.9},
        {"metric": "DCC", "direction": "up"},
    ],
    "rationale_metric_link": ["LCOM4"],
}
FILES = {"app/orders.py": "class Orders:\n    pass\n"}


@pytest.fixture
def prompt():
    return build_patch_prompt("app.orders:Orders", SUGGESTION, FILES)


class TestPatchPrompt:
    def test_carries_the_suggestion_and_the_code(self, prompt):
        assert "Extract the audit log" in prompt
        assert "Move record_audit and audit_trail" in prompt
        assert "### app/orders.py" in prompt
        assert "class Orders:" in prompt

    def test_never_carries_the_prediction(self, prompt):
        for word in ("expected_effect", "LCOM4", "DCC", "direction", "confidence", "0.9"):
            assert word not in prompt

    def test_never_carries_thresholds_or_measurements(self, prompt):
        whole = SYSTEM_INSTRUCTION + prompt
        for word in ("threshold", "[WARN]", "[CRITICAL]"):
            assert word not in whole

    def test_names_the_files_that_may_change(self, prompt):
        assert "app/orders.py" in prompt.split("### app/orders.py")[0]

    def test_a_new_file_may_be_allowed_without_content(self):
        prompt = build_patch_prompt(
            "app.orders:Orders", SUGGESTION, {**FILES, "app/audit.py": None}
        )
        assert "app/audit.py" in prompt
        assert "does not exist yet" in prompt

    def test_reads_what_advise_actually_writes(self):
        """Öneri `advise`'ın kendi sınıfından gelir; alan adı varsayılmaz.

        İlk gerçek koşuda prompt `details` alanını okuyordu ve öneri metni boş
        gidiyordu: `advise` metni `sketch` alanına yazar. Testler o zaman elle
        yazılmış bir sözlük kullandığı için hatayı görmedi.
        """
        from rlens.advise.advisor import Suggestion

        written = Suggestion(title="Split it", sketch="Move the audit methods out.").to_dict()
        prompt = build_patch_prompt("app.orders:Orders", written, FILES)
        assert "Move the audit methods out." in prompt

    def test_the_system_asks_for_the_narrowest_change(self):
        assert "nothing the suggestion does not say" in SYSTEM_INSTRUCTION
        assert "```diff" in SYSTEM_INSTRUCTION


DIFF = (
    "--- a/app/orders.py\n+++ b/app/orders.py\n@@ -1,2 +1,2 @@\n"
    "-class Orders:\n+class Orders(object):\n     pass\n"
)


class TestParsePatch:
    def test_one_diff_block(self):
        reply = f"Here is the change.\n```diff\n{DIFF}```\nDone."
        assert parse_patch(reply) == DIFF

    def test_a_patch_fence_is_accepted_too(self):
        assert parse_patch(f"```patch\n{DIFF}```") == DIFF

    def test_no_block_is_refused(self):
        with pytest.raises(PatchFormatError, match="no ```diff block"):
            parse_patch(DIFF)

    def test_two_blocks_are_refused(self):
        with pytest.raises(PatchFormatError, match="2 ```diff blocks"):
            parse_patch(f"```diff\n{DIFF}```\n```diff\n{DIFF}```")

    def test_an_empty_block_is_refused(self):
        with pytest.raises(PatchFormatError, match="empty"):
            parse_patch("```diff\n\n```")


class TestRepairPrompt:
    def test_carries_the_reason_and_the_rejected_patch(self, prompt):
        repair = build_repair_prompt(prompt, DIFF, "The patch does not apply cleanly: x")
        assert repair.startswith(prompt)
        assert "The patch does not apply cleanly: x" in repair
        assert DIFF in repair

    def test_a_long_rejected_patch_is_not_repeated(self, prompt):
        """Onarım istemi sağlayıcının token sınırını aşmasın (ilk gerçek koşu)."""
        long_patch = DIFF * 200
        repair = build_repair_prompt(prompt, long_patch, "corrupt patch at line 3")
        assert long_patch not in repair
        assert "corrupt patch at line 3" in repair
        assert "too long to repeat" in repair
