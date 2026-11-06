"""Real subprocess regressions for safe argument and lifetime handling."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from test_gate import gate


class ProcessSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    @unittest.skipUnless(os.name == "nt", "Windows batch-file argument boundary")
    def test_npm_shim_arguments_reach_node_literally(self):
        if not shutil.which("node"):
            self.skipTest("Node is required to exercise an npm tool")
        shim = self.root / "node_modules/.bin/tool.cmd"
        entry = self.root / "node_modules/tool/cli.js"
        shim.parent.mkdir(parents=True)
        entry.parent.mkdir(parents=True)
        entry.write_text(
            'require("fs").writeFileSync("args.json", JSON.stringify(process.argv.slice(2)));',
            encoding="utf-8",
        )
        shim.write_text('@echo off\n@SET "dp0=%~dp0"\nnode "%dp0%\\..\\tool\\cli.js" %*\n', encoding="utf-8")
        name = "x&echo.INJECTED&x.ts"
        code, output = gate.sh([str(shim), name], self.root, timeout=10)
        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads((self.root / "args.json").read_text()), [name])
        self.assertNotIn("INJECTED", output)

    @unittest.skipUnless(os.name == "nt", "Windows npm TypeScript shim")
    def test_extensionless_node_entry_preserves_a_real_runtime_failure(self):
        if not shutil.which("node"):
            self.skipTest("Node is required to exercise an npm tool")
        shim = self.root / "node_modules/.bin/tsc.cmd"
        entry = self.root / "node_modules/typescript/bin/tsc"
        shim.parent.mkdir(parents=True)
        entry.parent.mkdir(parents=True)
        entry.write_text('#!/usr/bin/env node\nrequire("vm").runInNewContext("const broken = ;");\n')
        shim.write_text('@echo off\n@SET "dp0=%~dp0"\nnode "%dp0%\\..\\typescript\\bin\\tsc" %*\n')
        code, output = gate.sh([str(shim)], self.root, timeout=10)
        self.assertEqual(code, 1, output)
        self.assertIn("SyntaxError", output)

    @unittest.skipUnless(os.name == "nt", "Windows batch-file argument boundary")
    def test_unknown_batch_files_are_not_shell_executed(self):
        shim = self.root / "unknown.cmd"
        shim.write_text("@echo off\nexit /b 0\n", encoding="utf-8")
        code, output = gate.sh([str(shim), "x&echo.INJECTED&x.ts"], self.root, timeout=5)
        self.assertNotEqual(code, 0)
        self.assertNotIn("INJECTED", output)

    def test_timeout_stops_descendant_and_preserves_stderr(self):
        child = "import pathlib,time;time.sleep(3);pathlib.Path('survivor').write_text('alive')"
        parent = (
            "import subprocess,sys,time;"
            "print('TIMEOUT_DIAGNOSTIC',file=sys.stderr,flush=True);"
            "subprocess.Popen([sys.executable,'-c'," + repr(child) + "],"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(30)"
        )
        started = time.monotonic()
        code, output = gate.sh([sys.executable, "-c", parent], self.root, timeout=1)
        elapsed = time.monotonic() - started
        time.sleep(3.2)
        self.assertEqual(code, 124)
        self.assertIn("TIMEOUT_DIAGNOSTIC", output)
        self.assertLess(elapsed, 10)
        self.assertFalse((self.root / "survivor").exists())

    def test_exited_parent_cannot_leave_descendant_holding_pipes(self):
        child = "import pathlib,time;time.sleep(3);pathlib.Path('survivor').write_text('alive')"
        parent = (
            "import subprocess,sys;"
            "print('EXITED_PARENT',file=sys.stderr,flush=True);"
            "subprocess.Popen([sys.executable,'-c'," + repr(child) + "])"
        )
        started = time.monotonic()
        code, output = gate.sh([sys.executable, "-c", parent], self.root, timeout=1)
        elapsed = time.monotonic() - started
        time.sleep(3.2)
        self.assertEqual(code, 124)
        self.assertIn("EXITED_PARENT", output)
        self.assertLess(elapsed, 2.5)
        self.assertFalse((self.root / "survivor").exists())

    def test_spawn_error_is_a_failed_check_not_an_exception(self):
        path = self.root / "invalid-executable"
        path.write_text("not an executable\n", encoding="utf-8")
        code, _ = gate.sh([str(path)], self.root, timeout=5)
        self.assertNotEqual(code, 0)

    def test_cargo_plugin_uses_resolved_pin_with_plugin_argument(self):
        (self.root / "nextest").write_text(
            "import json,sys;open('plugin-args.json','w').write(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        cfg = {"tools": {"cargo-nextest": sys.executable}}
        check = next(c for c in gate.builtin_checks() if c.id == "rust.test")
        plan = {"scope_changed": False, "ctx": {"files": {}}, "base": None, "changed": None}
        result = gate.run_check(self.root, cfg, check, plan, True, 10)
        self.assertEqual(result["status"], "pass", result["detail"])
        self.assertEqual(
            json.loads((self.root / "plugin-args.json").read_text()),
            ["run", "--workspace", "--no-tests=pass"],
        )


if __name__ == "__main__":
    unittest.main()
