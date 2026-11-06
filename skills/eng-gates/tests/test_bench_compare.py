"""Exercise the public benchmark-comparison CLI against real JSON files."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench_compare.py"


class BenchmarkComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / "base.json"
        self.current = self.root / "current.json"
        self.baseline.write_text('{"work": 100}', encoding="utf-8")

    def compare(self, current, *args):
        self.current.write_text(current, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.baseline), str(self.current), *args],
            capture_output=True, text=True,
        ).returncode

    def test_invalid_metrics_are_bad_input_not_successful_checks(self):
        for value in ("NaN", "Infinity", "-Infinity", "true", "false", "1e999"):
            with self.subTest(value=value):
                self.assertEqual(self.compare('{"work": ' + value + '}'), 2)

    def test_invalid_budget_cannot_hide_a_regression(self):
        for value in ("NaN", "Infinity", "-1"):
            with self.subTest(value=value):
                self.assertEqual(self.compare('{"work": 200}', "--max-regression", value), 2)

    def test_budget_boundary_and_metric_direction(self):
        for current, args, expected in (
            (105, (), 0),
            (106, (), 1),
            (96, ("--higher-is-better",), 0),
            (94, ("--higher-is-better",), 1),
        ):
            with self.subTest(current=current, args=args):
                self.assertEqual(self.compare('{"work": ' + str(current) + '}', *args), expected)

    def test_missing_benchmark_fails_unless_explicitly_allowed(self):
        self.assertEqual(self.compare("{}"), 1)
        self.assertEqual(self.compare("{}", "--allow-missing"), 0)


if __name__ == "__main__":
    unittest.main()
