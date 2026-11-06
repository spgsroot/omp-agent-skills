"""Consumer-visible gate regressions; only stdlib and a temporary Git repo."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import json


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("eng_gate", SCRIPTS / "gate.py")
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)


class GateRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")

    def git(self, *args):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run(
            ["git", "-c", "user.name=Gate Test", "-c", "user.email=gate@example.invalid", *args],
            cwd=self.root, env=env, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def baseline(self, files):
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "core.hooksPath=" + str(self.root / "no-hooks"), "commit", "-qm", "baseline")
        return self.git("rev-parse", "HEAD")

    def test_deleting_protected_file_fails_guard(self):
        base = self.baseline({"ruff.toml": "line-length = 88\n"})
        (self.root / "ruff.toml").unlink()
        changed = gate.changed_files(self.root, base)
        status, _ = gate.guard_config(self.root, {}, base, changed)
        self.assertEqual(status, "fail")

    def test_renaming_protected_file_fails_guard(self):
        base = self.baseline({"ruff.toml": "line-length = 88\n"})
        self.git("mv", "ruff.toml", "saved-config.txt")
        changed = gate.changed_files(self.root, base)
        status, _ = gate.guard_config(self.root, {}, base, changed)
        self.assertEqual(status, "fail")

    def test_deleting_embedded_gate_settings_fails_without_crashing(self):
        for name, text in (
            ("pyproject.toml", "[tool.ruff]\nline-length = 88\n"),
            ("package.json", '{"scripts":{"test":"vitest run"}}\n'),
        ):
            with self.subTest(name=name):
                base = self.baseline({name: text})
                (self.root / name).unlink()
                changed = gate.changed_files(self.root, base)
                status, _ = gate.guard_config(self.root, {}, base, changed)
                self.assertEqual(status, "fail")
                self.git("reset", "--hard", base)

    def test_deleted_source_still_runs_language_tests_not_file_linters(self):
        base = self.baseline({"pyproject.toml": "", "deleted.py": "answer = 42\n"})
        (self.root / "deleted.py").unlink()
        plan = gate.plan(self.root, {}, "fast", False, base)
        self.assertIn("python", plan["touched"])
        self.assertIsNone(gate.render("ruff check {files:python}", plan["ctx"]))
        check = gate.Check("py.test", "python", "fast", "tests", [("git", "git rev-parse --is-inside-work-tree")])
        result = gate.run_check(self.root, {}, check, plan, True, 10)
        self.assertEqual(result["status"], "pass")

    def test_init_preserves_existing_vendored_runner_unless_forced(self):
        vendored = self.root / "tools/eng-gates/gate.py"
        vendored.parent.mkdir(parents=True)
        vendored.write_text("local reviewed runner\n", encoding="utf-8")
        self.assertEqual(gate.cmd_init(self.root, False), 0)
        self.assertEqual(vendored.read_text(encoding="utf-8"), "local reviewed runner\n")
        self.assertEqual(gate.cmd_init(self.root, True), 0)
        self.assertEqual(vendored.read_bytes(), (SCRIPTS / "gate.py").read_bytes())

    def test_invalid_requested_base_is_a_configuration_error(self):
        self.baseline({"pyproject.toml": "", "example.py": "value = 1\n"})
        for cfg, override in (({}, "missing-ref"), ({"gate": {"base": "missing-ref"}}, None)):
            with self.subTest(cfg=cfg, override=override):
                with self.assertRaises(SystemExit) as error:
                    gate.resolve_base(self.root, cfg, override)
                self.assertEqual(error.exception.code, 2)

    def test_failed_git_diff_cannot_be_reported_as_no_changes(self):
        self.baseline({"example.py": "value = 1\n"})
        with self.assertRaises(SystemExit) as error:
            gate.changed_files(self.root, "missing-ref")
        self.assertEqual(error.exception.code, 2)

    def test_suppression_guard_handles_unicode_and_custom_diff_prefixes(self):
        base = self.baseline({"café.py": "value = 1\n", "plain.py": "value = 1\n"})
        self.git("config", "diff.noprefix", "true")
        self.git("config", "core.quotePath", "true")
        for name in ("café.py", "plain.py", "новый.py"):
            (self.root / name).write_text("value = 1  # noqa\n", encoding="utf-8")
        changed = gate.changed_files(self.root, base)
        status, detail = gate.guard_suppress(self.root, {}, base, changed)
        self.assertEqual(status, "fail")
        for name in ("café.py", "plain.py", "новый.py"):
            self.assertIn(name, detail)

    def test_human_snapshot_approves_nested_files_and_deletions_not_later_edits(self):
        base = self.baseline({
            "tools/eng-gates/check.py": "value = 1\n",
            "ruff.toml": "line-length = 88\n",
            "pyproject.toml": "[tool.ruff]\nline-length = 88\n",
        })
        nested = self.root / "tools/eng-gates/check.py"
        nested.write_text("value = 2\n", encoding="utf-8")
        (self.root / "ruff.toml").unlink()
        (self.root / "pyproject.toml").unlink()
        changed = gate.changed_files(self.root, base)
        snapshot = gate.protected_state(self.root, {}, base)
        path = gate.approval_path(self.root)
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with patch.dict(os.environ):
            os.environ.pop("CI", None)
            self.assertEqual(gate.guard_config(self.root, {}, base, changed)[0], "pass")
            nested.write_text("value = 3\n", encoding="utf-8")
            self.assertEqual(gate.guard_config(self.root, {}, base, changed)[0], "fail")
            nested.write_text("value = 2\n", encoding="utf-8")
            os.environ["CI"] = "1"
            self.assertEqual(gate.guard_config(self.root, {}, base, changed)[0], "fail")

    def test_config_only_edits_invalidate_whole_language_scope(self):
        base = self.baseline({
            "pyproject.toml": "", "example.py": "value = 1\n",
            "ruff.toml": "line-length = 88\n", "package.json": "{}",
            "tsconfig.strict.json": "{}",
        })
        (self.root / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
        (self.root / "tsconfig.strict.json").write_text('{"compilerOptions":{"strict":true}}', encoding="utf-8")
        plan = gate.plan(self.root, {}, "fast", False, base)
        self.assertIn("ts", plan["touched"])
        self.assertEqual(gate.render("ruff check {files:python}", plan["ctx"]), ["ruff", "check", "."])

    def test_vendored_init_can_restore_templates_and_add_a_language(self):
        (self.root / "pyproject.toml").write_text("", encoding="utf-8")
        gate.cmd_init(self.root, False)
        (self.root / "ruff.toml").unlink()
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        runner = self.root / "tools/eng-gates/gate.py"
        result = subprocess.run(
            [sys.executable, str(runner), "init", "--force", "-C", str(self.root)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "ruff.toml").is_file())
        self.assertTrue((self.root / "tsconfig.strict.json").is_file())

    def test_utf8_config_is_read_without_locale_decoding(self):
        (self.root / "gates.toml").write_text(
            '# Ø\n[gate]\nlanguages = ["python"]\n', encoding="utf-8"
        )
        result = subprocess.run(
            [sys.executable, "-X", "utf8=0", str(SCRIPTS / "gate.py"), "doctor", "-C", str(self.root)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_approve_honors_override_for_a_committed_deletion(self):
        base = self.baseline({"ruff.toml": "line-length = 88\n"})
        (self.root / "ruff.toml").unlink()
        self.baseline({"gates.toml": '[gate]\nbase = "missing-ref"\n'})
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        # Exercise the human command only inside this disposable consumer fixture.
        env = dict(os.environ)
        env.pop("ENG_GATES_AGENT", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "gate.py"), "approve", "--base", base, "-C", str(self.root)],
            env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        cfg = gate.load_config(self.root)
        with patch.dict(os.environ):
            os.environ.pop("CI", None)
            status, detail = gate.guard_config(self.root, cfg, base, gate.changed_files(self.root, base))
        self.assertEqual(status, "pass", detail)

    def test_rename_retains_old_suppressions_but_detects_new_ones(self):
        original = "value = 1  # noqa\nuntouched = 2\nstable = 3\n"
        base = self.baseline({"old.py": original})
        self.git("mv", "old.py", "new.py")
        changed = gate.changed_files(self.root, base)
        self.assertEqual(gate.guard_suppress(self.root, {}, base, changed)[0], "pass")
        (self.root / "new.py").write_text(original + "other = 2  # type: ignore\n")
        status, detail = gate.guard_suppress(self.root, {}, base, changed)
        self.assertEqual(status, "fail")
        self.assertIn("other = 2", detail)
        self.assertNotIn("value = 1", detail)

    def test_literal_filename_does_not_scan_an_ignored_glob_match(self):
        base = self.baseline({"example[1].py": "value = 1\n", "example1.py": "value = 1\n"})
        (self.root / "example[1].py").write_text("value = 2\n")
        (self.root / "example1.py").write_text("value = 2  # noqa\n")
        cfg = {"gate": {"suppress_ignore": ["example1.py"]}}
        status, detail = gate.guard_suppress(self.root, cfg, base, gate.changed_files(self.root, base))
        self.assertEqual(status, "pass", detail)

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain a colon")
    def test_pathspec_magic_is_a_literal_source_filename(self):
        name = ":(literal)example.py"
        base = self.baseline({name: "value = 1\n"})
        (self.root / name).write_text("value = 1  # noqa\n")
        status, detail = gate.guard_suppress(self.root, {}, base, gate.changed_files(self.root, base))
        self.assertEqual(status, "fail")
        self.assertIn(name, detail)


if __name__ == "__main__":
    unittest.main()
