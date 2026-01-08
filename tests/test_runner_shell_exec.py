import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from butlerai.runner.shell_exec import run_shell


class TestShellExec(unittest.TestCase):
    def test_success(self) -> None:
        res = run_shell(command="echo hello", timeout_ms=2000)
        self.assertEqual(res.exit_code, 0)
        self.assertIn("hello", res.stdout)

    def test_failure(self) -> None:
        res = run_shell(command="false", timeout_ms=2000)
        self.assertNotEqual(res.exit_code, 0)

    def test_timeout(self) -> None:
        res = run_shell(command="sleep 2", timeout_ms=10)
        self.assertTrue(res.timed_out)
        self.assertEqual(res.exit_code, 124)


if __name__ == "__main__":
    unittest.main()

