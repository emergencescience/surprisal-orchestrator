import os

from providers.base import ExecutionResult
from providers.docker import DockerExecutionProvider
from providers.http import HttpExecutionProvider
from services.safety import validate_code_safety


def execute_submission_sync(solution_code: str, evaluation_spec: str, language: str = "python3") -> ExecutionResult:
    """
    Dispatcher for code execution. Validates safety and selects the appropriate provider.
    """
    # 0. Safety Checks
    for code, label in [(solution_code, ""), (evaluation_spec, "Evaluation Spec Error: ")]:
        err = validate_code_safety(code, language)
        if err:
            return ExecutionResult(status="rejected", stderr=f"{label}{err}")

    # 1. Provider Selection
    if language == "javascript":
        js_url = os.getenv("JS_SANDBOX_URL")
        if js_url:
            return HttpExecutionProvider(js_url).execute(solution_code, evaluation_spec, language)

    if language == "python3":
        py_url = os.getenv("PYTHON_SANDBOX_URL")
        if py_url:
            return HttpExecutionProvider(py_url).execute(solution_code, evaluation_spec, language)

    # Default to Docker (Local/Dev)
    return DockerExecutionProvider().execute(solution_code, evaluation_spec, language)
