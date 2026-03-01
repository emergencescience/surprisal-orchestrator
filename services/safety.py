import ast


def validate_code_safety(code: str, language: str = "python3") -> str | None:
    """
    Statically analyzes code for dangerous patterns.
    Primarily for Python. For other languages, we rely on sandbox isolation.
    """
    if language != "python3":
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax Error: {e}"

    DANGEROUS_MODULES = {"os", "sys", "subprocess", "shutil", "importlib", "socket", "multiprocessing", "threading", "pty", "pickle"}
    DANGEROUS_BUILTINS = {"exec", "eval", "open", "__import__", "input"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in DANGEROUS_MODULES:
                    return f"Security Error: Import of '{alias.name}' is forbidden."
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in DANGEROUS_MODULES:
                return f"Security Error: Import from '{node.module}' is forbidden."
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in DANGEROUS_BUILTINS:
                return f"Security Error: Usage of '{node.func.id}' is forbidden."
    return None
