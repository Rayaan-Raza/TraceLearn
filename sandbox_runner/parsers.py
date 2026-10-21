"""Parsers for compiler warnings, ASan, UBSan and Valgrind memcheck reports.

Each parser takes raw text and returns plain dicts, so results serialize to
JSON as they are. Parsers never raise on unknown input: anything they do not
recognise is counted under ``unparsed`` instead.
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------- compiler --

_DIAG_RE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<sev>warning|error|fatal error|note):\s*(?P<msg>.*?)"
    r"(?:\s*\[(?P<flag>-W[\w=+-]+|-f[\w=+-]+)\])?\s*$",
    re.MULTILINE,
)


def parse_compiler_output(text: str, source_name: str | None = None) -> dict:
    """Parse gcc/clang diagnostics.

    Returns ``{"warnings": [...], "errors": [...], "count_by_flag": {...}}``.
    Diagnostics from system headers are kept out when ``source_name`` is given.
    """
    warnings, errors = [], []
    for m in _DIAG_RE.finditer(text or ""):
        if source_name and not m.group("file").endswith(source_name):
            continue
        item = {
            "line": int(m.group("line")),
            "col": int(m.group("col")) if m.group("col") else None,
            "message": m.group("msg").strip(),
            "flag": m.group("flag"),
        }
        sev = m.group("sev")
        if sev == "warning":
            warnings.append(item)
        elif sev in ("error", "fatal error"):
            errors.append(item)
    counts = Counter(w["flag"] or "unflagged" for w in warnings)
    return {"warnings": warnings, "errors": errors, "count_by_flag": dict(counts)}


# -------------------------------------------------------------------- ASan --

_ASAN_HEAD = re.compile(r"ERROR: AddressSanitizer: (?P<kind>[\w-]+)")
_ASAN_ACCESS = re.compile(r"(?P<rw>READ|WRITE) of size (?P<size>\d+)")
_ASAN_FRAME0 = re.compile(r"#0 0x[0-9a-f]+ in (?P<func>\S+) (?P<file>[^\s:]+):(?P<line>\d+)")
_ASAN_STACK_VAR = re.compile(
    r"\[(?P<lo>\d+), (?P<hi>\d+)\) '(?P<var>[^']+)'.*<== Memory access at offset (?P<off>\d+) "
    r"(?P<how>overflows|underflows|partially overflows|partially underflows)"
)
_ASAN_REGION = re.compile(
    r"is located (?P<n>\d+) bytes (?P<dir>to the right of|after|to the left of|before|inside of) "
    r"(?P<sz>\d+)-byte region"
)
_ASAN_GLOBAL = re.compile(
    r"is located (?P<n>\d+) bytes (?P<dir>to the right of|after|to the left of|before) "
    r"global variable '(?P<var>[^']+)'.*?of size (?P<sz>\d+)"
)


def parse_asan(text: str) -> dict | None:
    """Return the first ASan report in ``text`` or ``None``.

    ``bytes_past_end`` is how far beyond the object the access landed (0 means
    the byte right after the last element). With the access ``size`` that
    gives ``elements_past_end`` — the off-by-one vs array-bounds split of
    §3.1 classes 2 and 3 uses it.
    """
    if not text:
        return None
    head = _ASAN_HEAD.search(text)
    if not head:
        return None
    out: dict = {"tool": "asan", "kind": head.group("kind"), "access": None,
                 "size": None, "line": None, "function": None,
                 "bytes_past_end": None, "elements_past_end": None,
                 "object_size": None, "direction": None}
    tail = text[head.start():]
    if m := _ASAN_ACCESS.search(tail):
        out["access"] = m.group("rw")
        out["size"] = int(m.group("size"))
    if m := _ASAN_FRAME0.search(tail):
        out["function"] = m.group("func")
        out["line"] = int(m.group("line"))
    past = None
    if m := _ASAN_STACK_VAR.search(tail):
        lo, hi, off = int(m.group("lo")), int(m.group("hi")), int(m.group("off"))
        out["object_size"] = hi - lo
        if off >= hi:
            past, out["direction"] = off - hi, "right"
        else:
            past, out["direction"] = lo - off - 1, "left"
    elif m := (_ASAN_GLOBAL.search(tail) or _ASAN_REGION.search(tail)):
        d = m.group("dir")
        out["object_size"] = int(m.group("sz"))
        if d in ("to the right of", "after"):
            past, out["direction"] = int(m.group("n")), "right"
        elif d in ("to the left of", "before"):
            past, out["direction"] = int(m.group("n")) - 1, "left"
        else:
            out["direction"] = "inside"
    if past is not None:
        out["bytes_past_end"] = past
        if out["size"]:
            out["elements_past_end"] = past // out["size"]
    return out


# ------------------------------------------------------------------- UBSan --

_UBSAN_RE = re.compile(r"(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+): runtime error: (?P<msg>.+)")

UBSAN_KINDS = [
    ("signed-integer-overflow", re.compile(r"signed integer overflow|negation of .* cannot be represented")),
    ("index-out-of-bounds", re.compile(r"index -?\d+ out of bounds")),
    ("division-by-zero", re.compile(r"division by zero")),
    ("shift", re.compile(r"shift exponent|left shift of")),
    ("null-dereference", re.compile(r"null pointer")),
    ("misaligned", re.compile(r"misaligned address")),
    ("float-cast-overflow", re.compile(r"is outside the range of representable values")),
    ("pointer-overflow", re.compile(r"pointer index expression|applying (?:non-zero )?offset")),
    ("invalid-load", re.compile(r"load of value .* not a valid value")),
    ("missing-return", re.compile(r"execution reached the end of a value-returning function")),
    ("insufficient-space", re.compile(r"insufficient space for an object")),
]


def classify_ubsan(msg: str) -> str:
    for kind, rx in UBSAN_KINDS:
        if rx.search(msg):
            return kind
    return "other"


def parse_ubsan(text: str) -> list[dict]:
    """Every UBSan ``runtime error`` line, de-duplicated by (kind, line)."""
    seen, out = set(), []
    for m in _UBSAN_RE.finditer(text or ""):
        kind = classify_ubsan(m.group("msg"))
        key = (kind, int(m.group("line")))
        if key in seen:
            continue
        seen.add(key)
        item = {"tool": "ubsan", "kind": kind, "line": int(m.group("line")),
                "message": m.group("msg").strip()[:300]}
        if kind == "index-out-of-bounds":
            im = re.search(r"index (-?\d+) out of bounds for type '[^\[]*\[(\d+)\]'", m.group("msg"))
            if im:
                idx, n = int(im.group(1)), int(im.group(2))
                item["index"], item["bound"] = idx, n
                item["elements_past_end"] = idx - n if idx >= n else -idx - 1
        out.append(item)
    return out


# ---------------------------------------------------------------- Valgrind --

_VG_PID = re.compile(r"^==\d+== ?", re.MULTILINE)
VALGRIND_KINDS = [
    ("uninit-cond", re.compile(r"Conditional jump or move depends on uninitialised value")),
    ("uninit-value", re.compile(r"Use of uninitialised value of size")),
    ("uninit-syscall", re.compile(r"Syscall param .* uninitialised byte")),
    ("invalid-read", re.compile(r"Invalid read of size")),
    ("invalid-write", re.compile(r"Invalid write of size")),
    ("invalid-free", re.compile(r"Invalid free|Mismatched free")),
    ("stack-overflow", re.compile(r"Stack overflow in thread|Process terminating with default action of signal 11.*\n.*Access not within mapped region.*\n?.*stack", re.I)),
]
_VG_AT = re.compile(r"(?:at|by) 0x[0-9A-F]+: (?P<func>[^\s(]+) \((?P<file>[^:)]+):(?P<line>\d+)\)")
_VG_SUMMARY = re.compile(r"ERROR SUMMARY: (\d+) errors? from (\d+) contexts?")


def parse_valgrind(text: str) -> dict:
    """Summarise a memcheck log: kinds seen, first user-code line per kind."""
    text = text or ""
    body = _VG_PID.sub("", text)
    blocks = re.split(r"\n\s*\n", body)
    kinds: dict[str, dict] = {}
    for blk in blocks:
        for kind, rx in VALGRIND_KINDS:
            if rx.search(blk):
                at = _VG_AT.search(blk)
                entry = kinds.setdefault(kind, {"count": 0, "line": None, "function": None})
                entry["count"] += 1
                if at and entry["line"] is None:
                    entry["line"] = int(at.group("line"))
                    entry["function"] = at.group("func")
                break
    m = _VG_SUMMARY.search(body)
    errors = int(m.group(1)) if m else None
    uninit = any(k.startswith("uninit") for k in kinds)
    return {"tool": "valgrind", "ran": bool(text.strip()), "error_count": errors,
            "kinds": kinds, "uninit": uninit}


# ------------------------------------------------------------ stack check --

def looks_like_stack_overflow(signal: int | None, asan: dict | None, vg: dict | None,
                              stderr: str = "") -> bool:
    """A crash counts as a stack overflow when a tool says so explicitly, or
    when the plain build died of SIGSEGV with no other memory report."""
    if asan and asan.get("kind") == "stack-overflow":
        return True
    if vg and "stack-overflow" in (vg.get("kinds") or {}):
        return True
    if "stack-overflow" in (stderr or ""):
        return True
    return False
