from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
import sys
import importlib.util
from typing import Iterable


@dataclass
class AuditResult:
    name: str
    status: str
    summary: str
    command: str
    output: str


def _command_text(command: Iterable[str]) -> str:
    return " ".join(command)


def _run_command(name: str, command: list[str], cwd: str, timeout: int = 120) -> AuditResult:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except OSError as ex:
        return AuditResult(
            name=name,
            status="error",
            summary=str(ex),
            command=_command_text(command),
            output=str(ex),
        )
    except subprocess.TimeoutExpired:
        return AuditResult(
            name=name,
            status="timeout",
            summary="Timed out",
            command=_command_text(command),
            output="Timed out while running tool.",
        )

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    output = output.strip()
    if proc.returncode == 0:
        summary = "OK"
        if output:
            first = output.splitlines()[0].strip()
            if first:
                summary = first[:180]
        return AuditResult(name=name, status="ok", summary=summary, command=_command_text(command), output=output)
    summary = output.splitlines()[0].strip()[:180] if output else f"Exited with code {proc.returncode}"
    return AuditResult(name=name, status="issue", summary=summary, command=_command_text(command), output=output)


def _tool_missing(name: str, command: list[str]) -> AuditResult:
    return AuditResult(
        name=name,
        status="missing",
        summary=f"{command[0]} not installed",
        command=_command_text(command),
        output="Tool not available on PATH.",
    )


def run_project_audit(project_root: str, target_file: str) -> list[AuditResult]:
    project_root = os.path.abspath(project_root)
    target_file = os.path.abspath(target_file)
    commands: list[tuple[str, list[str]]] = [
        ("py_compile", [sys.executable, "-m", "py_compile", target_file]),
        ("ruff", [sys.executable, "-m", "ruff", "check", target_file]),
        ("mypy", [sys.executable, "-m", "mypy", "--follow-imports=silent", target_file]),
        ("pylint", [sys.executable, "-m", "pylint", "--score=n", target_file]),
    ]
    results: list[AuditResult] = []
    for name, command in commands:
        executable = command[0]
        module_name = command[2] if len(command) > 2 and command[1] == "-m" else ""
        if executable == sys.executable and module_name:
            if importlib.util.find_spec(module_name) is None:
                results.append(_tool_missing(name, command))
                continue
        elif executable != sys.executable and shutil.which(executable) is None:
            results.append(_tool_missing(name, command))
            continue
        results.append(_run_command(name, command, cwd=project_root))
    return results
