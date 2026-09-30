from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence


@dataclass(slots=True)
class ProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    def evidence(self) -> dict[str, object]:
        return {
            "argv": self.argv,
            "returncode": self.returncode,
            "stdout": self.stdout[-8000:],
            "stderr": self.stderr[-8000:],
        }


def run_checked(argv: Sequence[str | Path], *, cwd: Path, timeout: float = 15.0) -> ProcessResult:
    args = [str(x) for x in argv]
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=None,
    )
    return ProcessResult(args, completed.returncode, completed.stdout, completed.stderr)
