import os
import sys
import unittest
from unittest.mock import patch

from providers.base import ExecutionResult

# Add the parent directory (api) to sys.path so we can import execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.execution import execute_submission_sync


class TestExecution(unittest.TestCase):
    @patch("services.execution.DockerExecutionProvider.execute")
    def test_pass(self, mock_execute):
        mock_execute.return_value = ExecutionResult(status="accepted", stdout="ok", stderr="")
        solution = "def add(a, b): return a + b"
        test = """
import unittest
from solution import add
class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
"""
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "accepted")

    @patch("services.execution.DockerExecutionProvider.execute")
    def test_fail(self, mock_execute):
        mock_execute.return_value = ExecutionResult(status="rejected", stdout="", stderr="AssertionError")
        solution = "def add(a, b): return a - b"
        test = """
import unittest
from solution import add
class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
"""
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")

    @patch("services.execution.DockerExecutionProvider.execute")
    def test_timeout(self, mock_execute):
        mock_execute.return_value = ExecutionResult(status="rejected", stdout="", stderr="Execution timed out.")
        # We need the solution to actually run.
        # But wait, execute_submission_sync runs 'python -m unittest test_solution.py'.
        # 'test_solution.py' imports 'solution'.
        # If 'solution' has top-level infinite loop, it will hang on import.
        solution = "while True: pass"
        test = """
import unittest
import solution
class TestLoop(unittest.TestCase):
    def test_loop(self):
        pass
"""
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("timed out", result.stderr)

    def test_syntax_error(self):
        solution = "def add(a, b): return a +"
        test = """
import unittest
import solution
class TestSyntax(unittest.TestCase):
    def test_nothing(self):
        pass
"""
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")

    def test_security_import_os(self):
        solution = "import os\ndef foo(): pass"
        test = "pass"
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("Security Error: Import of 'os' is forbidden", result.stderr)

    def test_security_from_sys_import(self):
        solution = "from sys import exit\ndef foo(): pass"
        test = "pass"
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("Security Error: Import from 'sys' is forbidden", result.stderr)

    def test_security_builtin_open(self):
        solution = "f = open('test.txt', 'w')"
        test = "pass"
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("Security Error: Usage of 'open' is forbidden", result.stderr)

    def test_security_builtin_eval(self):
        solution = "eval('print(1)')"
        test = "pass"
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("Security Error: Usage of 'eval' is forbidden", result.stderr)

    def test_security_in_evaluation_spec(self):
        solution = "pass"
        test = "import os"
        result = execute_submission_sync(solution, test)
        self.assertEqual(result.status, "rejected")
        self.assertIn("Evaluation Spec Error: Security Error: Import of 'os' is forbidden", result.stderr)

    @patch("services.execution.DockerExecutionProvider.execute")
    def test_pass_js(self, mock_execute):
        mock_execute.return_value = ExecutionResult(status="accepted", stdout="JS OK", stderr="")
        solution = "function add(a, b) { return a + b; } module.exports = { add };"
        test = """
const { add } = require('./solution');
const assert = require('assert');
assert.strictEqual(add(1, 2), 3);
console.log('JS OK');
"""
        result = execute_submission_sync(solution, test, language="javascript")
        self.assertEqual(result.status, "accepted")
        self.assertIn("JS OK", result.stdout)
