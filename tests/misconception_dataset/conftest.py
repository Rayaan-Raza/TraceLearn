import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# sandbox_runner imports fcntl (Unix-only); the sandbox targets Linux/Docker
# (its CI runs on ubuntu). On Windows the modules cannot even be imported, so
# skip them at collection instead of erroring the whole suite (integration
# fix from the three-lane merge, 2026-10-23).
if sys.platform != "linux":
    collect_ignore = [
        "test_sandbox_runner.py",
        "test_docker_backend.py",
        "test_lfs_and_repairs.py",
        "test_sandbox_parsers.py",
    ]
