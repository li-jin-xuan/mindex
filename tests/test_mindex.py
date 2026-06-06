from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from install import managed_block, replace_block  # noqa: E402
from mindex_core import (  # noqa: E402
    atomic_write,
    configure_utf8_output,
    discover,
    memory_lock,
    parse_frontmatter,
    render_index,
    validate,
)


class MIndexTests(unittest.TestCase):
    def test_configure_utf8_output(self) -> None:
        configure_utf8_output()
        self.assertEqual(sys.stdout.encoding.casefold(), "utf-8")

    def test_frontmatter_requires_opening_at_start(self) -> None:
        metadata, body = parse_frontmatter("intro\n---\ntitle: wrong\n---\nbody")
        self.assertEqual(metadata, {})
        self.assertTrue(body.startswith("intro"))

    def test_nested_and_spaced_paths_are_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "projects" / "client work" / "alpha beta.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "---\ntitle: Alpha | Beta\nstatus: active\nupdated: 2026-06-06\n---\nBody\n",
                encoding="utf-8",
            )
            entries, warnings = discover(base)
            index = render_index(entries, datetime(2026, 6, 6))
            self.assertEqual(warnings, [])
            self.assertIn("projects/client work/alpha beta.md", index)
            self.assertIn("projects/client%20work/alpha%20beta.md", index)
            self.assertIn(r"Alpha \| Beta", index)

    def test_validation_rejects_real_invalid_dates_and_missing_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "projects" / "bad.md"
            path.parent.mkdir()
            path.write_text(
                "---\ntitle: Bad\nstatus: active\nupdated: 2026-02-31\n"
                "depends_on: [missing]\n---\nBody\n",
                encoding="utf-8",
            )
            entries, _ = discover(base)
            errors = validate(entries)
            self.assertTrue(any("无效日期" in error for error in errors))
            self.assertTrue(any("不存在的 id" in error for error in errors))

    def test_parse_frontmatter_valid(self) -> None:
        """Positive control: valid frontmatter is parsed correctly."""
        metadata, body = parse_frontmatter(
            "---\ntitle: Test\nstatus: active\nupdated: 2026-06-06\n---\nBody text\n"
        )
        self.assertEqual(metadata.get("title"), "Test")
        self.assertEqual(metadata.get("status"), "active")
        self.assertEqual(metadata.get("updated"), "2026-06-06")
        self.assertEqual(body.strip(), "Body text")

    def test_atomic_write_preserves_content(self) -> None:
        """atomic_write writes and replaces content correctly."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test.md"
            content = "---\ntitle: Atomic\nstatus: active\nupdated: 2026-06-06\n---\nTest body\n"
            atomic_write(target, content)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), content)

    def test_memory_lock_acquire_release(self) -> None:
        """memory_lock acquires and releases without error."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with memory_lock(base, blocking=False):
                pass  # Should not raise
            # Lock should be released (but file may persist)
            # Second lock should also work (first was released)
            with memory_lock(base, blocking=False):
                pass

    def test_memory_lock_blocks_another_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with memory_lock(Path(directory)):
                script = (
                    "import sys\n"
                    f"sys.path.insert(0, {str(TOOLS)!r})\n"
                    "from pathlib import Path\n"
                    "from mindex_core import memory_lock\n"
                    "try:\n"
                    f"    with memory_lock(Path({directory!r}), blocking=False): pass\n"
                    "except (BlockingIOError, OSError):\n"
                    "    raise SystemExit(23)\n"
                )
                result = subprocess.run([sys.executable, "-c", script], check=False, timeout=5)
                self.assertEqual(result.returncode, 23)

    def test_validate_happy_path(self) -> None:
        """validate returns no errors for a perfectly valid entry."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "projects" / "valid.md"
            path.parent.mkdir()
            path.write_text(
                "---\ntitle: Valid Project\nstatus: active\nupdated: 2026-06-06\n---\nBody\n",
                encoding="utf-8",
            )
            entries, _ = discover(base)
            errors = validate(entries)
            self.assertEqual(errors, [])

    def test_discover_skips_hidden_directories(self) -> None:
        """Files inside hidden directories should not appear in index."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / ".hidden" / "secret.md"
            path.parent.mkdir()
            path.write_text(
                "---\ntitle: Secret\nstatus: active\nupdated: 2026-06-06\n---\nBody\n",
                encoding="utf-8",
            )
            entries, warnings = discover(base)
            self.assertFalse(any("secret" in entry.path for entry in entries))

    def test_discover_skips_repository_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ("README.md", "CONTRIBUTING.md", "SECURITY.md"):
                (base / name).write_text(f"# {name}\n", encoding="utf-8")
            entries, warnings = discover(base)
            self.assertEqual(entries, [])
            self.assertEqual(warnings, [])

    def test_discover_skips_plugin_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "plugin" / "skills" / "remember" / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("---\ndescription: Plugin skill\n---\nBody\n", encoding="utf-8")
            entries, warnings = discover(base)
            self.assertEqual(entries, [])
            self.assertEqual(warnings, [])

    def test_discover_rejects_sensitive_filenames_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "projects" / "Production-API-Keys.md"
            path.parent.mkdir()
            path.write_text(
                "---\ntitle: Must not index\nstatus: active\nupdated: 2026-06-06\n---\nsecret\n",
                encoding="utf-8",
            )
            entries, warnings = discover(base)
            self.assertEqual(entries, [])
            self.assertTrue(any("疑似敏感文件" in warning for warning in warnings))

    def test_installer_is_idempotent_and_preserves_user_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mindex_") as directory:
            block = managed_block(Path(directory))
            original = "# Existing user instructions\n"
            installed = replace_block(original, block)
            self.assertEqual(replace_block(installed, block), installed)
            self.assertIn(original.strip(), installed)
            self.assertEqual(replace_block(installed, None), original)


if __name__ == "__main__":
    unittest.main()
