import os
import subprocess
import tempfile
import uuid

from .base import ExecutionProvider, ExecutionResult


class DockerExecutionProvider(ExecutionProvider):
    def execute(self, solution: str, spec: str, language: str) -> ExecutionResult:
        if os.getenv("SKIP_SANDBOX") == "true":
            return ExecutionResult(status="failed", stderr="[SYSTEM]: Sandbox execution is disabled (SKIP_SANDBOX=true).")

        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
        except subprocess.CalledProcessError, FileNotFoundError:
            return ExecutionResult(status="failed", stderr="[SYSTEM]: Sandbox Runtime Unavailable (Docker missing).")

        with tempfile.TemporaryDirectory() as tmpdir:
            if language == "python3":
                sol_file, spec_file = "solution.py", "evaluation_spec.py"
                cmd = ["python3", "-m", "unittest", "evaluation_spec"]
            elif language == "javascript":
                sol_file, spec_file = "solution.js", "evaluation_spec.js"
                cmd = ["node", spec_file]
            else:
                return ExecutionResult(status="rejected", error=f"Language {language} not supported.")

            with open(os.path.join(tmpdir, sol_file), "w") as f:
                f.write(solution)
            with open(os.path.join(tmpdir, spec_file), "w") as f:
                f.write(spec)

            container_name = f"surprisal-sandbox-{uuid.uuid4().hex[:8]}"
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "1.0",
                "-v",
                f"{tmpdir}:/home/sandbox:ro",
                "surprisal-sandbox",
                *cmd,
            ]

            try:
                result = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=12)
                return ExecutionResult(status="accepted" if result.returncode == 0 else "rejected", stdout=result.stdout, stderr=result.stderr)
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", container_name], capture_output=True)
                return ExecutionResult(status="rejected", stderr="Execution timed out.")
            except Exception as e:
                return ExecutionResult(status="rejected", stderr=str(e), error=str(e))
            finally:
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
