# SPDX-License-Identifier: Apache-2.0
"""Offline regression guards for the pinned PR scanner and publisher boundary.

These source-contract checks do not run scanners, install tools, contact providers,
create signing keys, or establish runtime/publication qualification.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "hf-space.yml"
SCANNER = (
    "szl-holdings/.github/.github/workflows/reusable-workflow-lint.yml@"
    "c26bce92867766c154e16a36a30823c9ed38022b"
)


def job_block(text: str, name: str) -> str:
    """Read one top-level job from this repository's block-style workflow."""
    pattern = rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)"
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(f"Required job is missing: {name}")
    return match.group(1)


class WorkflowScannerAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.scanner = job_block(cls.text, "validate-workflow")

    def test_scanner_uses_the_admitted_fail_closed_revision(self) -> None:
        refs = re.findall(r"^    uses: (\S+)\s*$", self.scanner, re.MULTILINE)
        self.assertEqual(refs, [SCANNER])

    def test_scanner_remains_pr_only(self) -> None:
        self.assertIn("    if: github.event_name == 'pull_request'\n", self.scanner)

    def test_caller_does_not_change_the_warning_threshold(self) -> None:
        self.assertIn("      fail-on-zizmor-warning: false\n", self.scanner)

    def test_caller_keeps_only_existing_scoped_permissions(self) -> None:
        match = re.search(
            r"(?m)^    permissions:\n((?:      [^\n]+\n)+)", self.scanner
        )
        self.assertIsNotNone(match)
        self.assertEqual(
            match.group(1),
            "      contents: read\n      security-events: write\n",
        )
        self.assertNotIn("secrets: inherit", self.scanner)

    def test_publisher_resolution_requires_main_and_non_pr_event(self) -> None:
        block = job_block(self.text, "resolve-publisher")
        guard = block.split("    needs:", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", guard)
        self.assertIn(
            "(github.event_name == 'push' || github.event_name == 'workflow_dispatch')",
            guard,
        )

    def test_publish_requires_main_non_pr_event_and_resolved_local_owner(self) -> None:
        block = job_block(self.text, "publish")
        guard = block.split("    needs:", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", guard)
        self.assertIn(
            "(github.event_name == 'push' || github.event_name == 'workflow_dispatch')",
            guard,
        )
        self.assertIn("needs.resolve-publisher.outputs.mode == 'local'", guard)

    def test_live_source_probe_remains_excluded_from_prs(self) -> None:
        block = job_block(self.text, "probe-live-official-sources")
        guard = block.split("    needs:", 1)[0]
        self.assertIn("github.event_name != 'pull_request'", guard)
        self.assertIn("needs.resolve-publisher.outputs.mode == 'local'", guard)

    def test_shared_hub_write_lock_is_preserved(self) -> None:
        for name in ("resolve-publisher", "publish"):
            with self.subTest(job=name):
                block = job_block(self.text, name)
                self.assertIn(
                    "      group: hf-write/space/SZLHOLDINGS/vertical-services\n",
                    block,
                )
                self.assertIn("      cancel-in-progress: false\n", block)


if __name__ == "__main__":
    unittest.main()
