"""sandbox_runner — the shared C/C++ execution harness (Master Plan §5, §9.2-U0).

Owner: Umaima (Lane B). Every lane imports it; nobody re-implements execution.

    from sandbox_runner import run_submission, RunConfig
    res = run_submission(code, "cpp", [{"input": "3\\n", "output": "6\\n"}])
    res["tests"]["passed"], res["warnings"]["count_by_flag"], res["runtime"]["sanitizer"]
"""

from .config import SANDBOX_VERSION, Limits, RunConfig, normalize_lang
from .runner import TestCase, cache_key, run_many, run_submission

__all__ = ["SANDBOX_VERSION", "Limits", "RunConfig", "TestCase", "cache_key",
           "normalize_lang", "run_many", "run_submission"]
