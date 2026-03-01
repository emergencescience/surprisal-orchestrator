import ast
import os
import subprocess
import tempfile
import uuid

from pydantic import BaseModel


class ExecutionResult(BaseModel):
    status: str  # "accepted", "rejected", "failed"
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None

def validate_code_safety(code: str, language: str = "python3") -> str | None:
    """
    Statically analyzes code for dangerous patterns.
    Primarily for Python. For other languages, we rely on Docker isolation.
    """
    if language != "python3":
        return None # Rely on Docker for JS/Rust for now

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax Error: {e}"

    DANGEROUS_MODULES = {
        'os', 'sys', 'subprocess', 'shutil', 'importlib', 'socket', 
        'multiprocessing', 'threading', 'pty', 'pickle'
    }
    DANGEROUS_BUILTINS = {'exec', 'eval', 'open', '__import__', 'input'}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in DANGEROUS_MODULES:
                    return f"Security Error: Import of '{alias.name}' is forbidden."
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in DANGEROUS_MODULES:
                return f"Security Error: Import from '{node.module}' is forbidden."
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DANGEROUS_BUILTINS:
                    return f"Security Error: Usage of '{node.func.id}' is forbidden."
    return None

def execute_submission_sync(
    solution_code: str, 
    evaluation_spec: str, 
    language: str = "python3"
) -> ExecutionResult:
    """
    Executes the solution code against the evaluation spec inside a Docker sandbox.
    Currently restricted to Python3.
    """
    
    # 0. Static Security Check (Python only)
    error = validate_code_safety(solution_code, language)
    if error:
        return ExecutionResult(status="rejected", stderr=error)
    
    error = validate_code_safety(evaluation_spec, language)
    if error:
        return ExecutionResult(status="rejected", stderr=f"Evaluation Spec Error: {error}")

    if language != "python3":
        return ExecutionResult(status="rejected", error=f"Language '{language}' not supported in Phase 1.")

    # 1. Environment Check: Verify Docker is available
    if os.getenv("SKIP_SANDBOX") == "true":
         return ExecutionResult(
            status="failed", 
            stderr="[SYSTEM]: Sandbox execution is disabled in this environment (SKIP_SANDBOX=true)."
        )

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ExecutionResult(
            status="failed", 
            stderr="[SYSTEM]: Sandbox Runtime Unavailable. Host is preparing for live execution (ETA: 1 week)."
        )

    # 2. Prepare Sandbox Files
    with tempfile.TemporaryDirectory() as tmpdir:
        solution_filename = "solution.py"
        spec_filename = "evaluation_spec.py"
        # Runner command: python3 -m unittest evaluation_spec
        cmd = ["python3", "-m", "unittest", "evaluation_spec"]

        # Write files
        with open(os.path.join(tmpdir, solution_filename), "w") as f:
            f.write(solution_code)
        with open(os.path.join(tmpdir, spec_filename), "w") as f:
            f.write(evaluation_spec)
            
        # 3. Run in Docker Container
        container_name = f"surprisal-sandbox-{uuid.uuid4().hex[:8]}"
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-v", f"{tmpdir}:/home/sandbox:ro",
            "surprisal-sandbox",
            *cmd
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=12
            )
            
            if result.returncode == 0:
                return ExecutionResult(
                    status="accepted",
                    stdout=result.stdout,
                    stderr=result.stderr
                )
            else:
                return ExecutionResult(
                    status="rejected",
                    stdout=result.stdout,
                    stderr=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", container_name], capture_output=True)
            return ExecutionResult(
                status="rejected",
                stderr="Execution timed out (Sandbox killed)."
            )
        except Exception as e:
            return ExecutionResult(
                status="rejected",
                stderr=f"Sandbox System Error: {str(e)}",
                error=str(e)
            )
        finally:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
