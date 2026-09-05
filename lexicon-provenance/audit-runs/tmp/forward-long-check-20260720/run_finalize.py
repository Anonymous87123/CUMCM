import subprocess
import sys
from pathlib import Path


case = sys.argv[1]
root = Path(__file__).resolve().parent
scripts = {
    "normal": root / "check_normal.py",
    "detached": root / "spawn_detached.py",
    "failure": root / "check_failure.py",
}
check_command = subprocess.list2cmdline([sys.executable, "-B", str(scripts[case])])
finalizer = (
    Path.home()
    / ".codex"
    / "skills"
    / "humanize-academic-chinese"
    / "scripts"
    / "finalize_humanize_long_document.py"
)
completed = subprocess.run(
    [
        sys.executable,
        "-B",
        str(finalizer),
        "--run-dir",
        str(root / case),
        "--rewrites",
        str(root / f"{case}-rewrites"),
        "--check-command",
        check_command,
        "--format",
        "text",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
stdout_lines = completed.stdout.splitlines()
print(f"PROCESS_EXIT={completed.returncode}")
print(f"STDOUT_FIRST={stdout_lines[0] if stdout_lines else '<EMPTY>'}")
if completed.stderr:
    print("STDERR=" + completed.stderr.rstrip())
