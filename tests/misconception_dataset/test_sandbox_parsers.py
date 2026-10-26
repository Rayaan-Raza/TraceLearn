"""Parser fixtures on canned reports — no compiler needed (gate G2)."""

from sandbox_runner import parsers
from sandbox_runner.compare import compare_output

ASAN_STACK = """=================================================================
==19==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffd53e4dda4 at pc 0x5c9e15fc837d bp 0x7ffd53e4dd60 sp 0x7ffd53e4dd50
READ of size 4 at 0x7ffd53e4dda4 thread T0
    #0 0x5c9e15fc837c in main /tmp/t.cpp:7
    #1 0x71afd3229d8f  (/lib/x86_64-linux-gnu/libc.so.6+0x29d8f)

Address 0x7ffd53e4dda4 is located in stack of thread T0 at offset 52 in frame
    #0 0x5c9e15fc8278 in main /tmp/t.cpp:1

  This frame has 1 object(s):
    [32, 40) 'a' (line 1) <== Memory access at offset 52 overflows this variable
SUMMARY: AddressSanitizer: stack-buffer-overflow /tmp/t.cpp:7 in main
"""

ASAN_HEAP_OLD = """==7==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000020
WRITE of size 4 at 0x602000000020 thread T0
    #0 0x4011 in fill /w/main.cpp:12
0x602000000020 is located 0 bytes to the right of 16-byte region [0x602000000010,0x602000000020)
"""

ASAN_HEAP_NEW = """==7==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000028
READ of size 4 at 0x602000000028 thread T0
    #0 0x4011 in main /w/main.cpp:3
0x602000000028 is located 8 bytes after 16-byte region [0x602000000010,0x602000000020)
"""

ASAN_GLOBAL = """==9==ERROR: AddressSanitizer: global-buffer-overflow on address 0x55
READ of size 4 at 0x55 thread T0
    #0 0x1 in main /w/main.cpp:9
0x55 is located 4 bytes after global variable 'arr' defined in 'main.cpp:2:5' (0x51) of size 40
"""

ASAN_STACKOVF = """==3==ERROR: AddressSanitizer: stack-overflow on address 0x7ffe (pc 0x55 bp 0x7f sp 0x7f T0)
    #0 0x55 in f(long long) /w/main.cpp:2
"""

UBSAN = """main.cpp:5:12: runtime error: signed integer overflow: 1000000000 * 10 cannot be represented in type 'int'
main.cpp:5:12: runtime error: signed integer overflow: 1410065408 * 10 cannot be represented in type 'int'
main.cpp:9:3: runtime error: index 10 out of bounds for type 'int [10]'
main.cpp:11:7: runtime error: division by zero
"""

VG = """==123== Memcheck, a memory error detector
==123== Conditional jump or move depends on uninitialised value(s)
==123==    at 0x109189: main (main.c:4)
==123==
==123== Use of uninitialised value of size 8
==123==    at 0x48D2B1A: _itoa_word (_itoa.c:180)
==123==    by 0x109199: main (main.c:5)
==123==
==123== ERROR SUMMARY: 5 errors from 2 contexts (suppressed: 0 from 0)
"""

GCC = """main.cpp: In function 'int main()':
main.cpp:4:11: warning: suggest parentheses around assignment used as truth value [-Wparentheses]
main.cpp:6:9: warning: 's' may be used uninitialized [-Wmaybe-uninitialized]
/usr/include/c++/13/bits/stl_vector.h:100:3: warning: something in a header [-Wfoo]
main.cpp:9:1: error: expected ';' before '}' token
"""


def test_asan_stack_bytes_past_end():
    r = parsers.parse_asan(ASAN_STACK)
    assert r["kind"] == "stack-buffer-overflow" and r["access"] == "READ"
    assert r["line"] == 7 and r["object_size"] == 8
    assert r["bytes_past_end"] == 12 and r["elements_past_end"] == 3


def test_asan_heap_both_wordings():
    a = parsers.parse_asan(ASAN_HEAP_OLD)
    b = parsers.parse_asan(ASAN_HEAP_NEW)
    assert a["elements_past_end"] == 0 and a["function"] == "fill" and a["line"] == 12
    assert b["elements_past_end"] == 2 and b["object_size"] == 16


def test_asan_global_and_stack_overflow():
    g = parsers.parse_asan(ASAN_GLOBAL)
    assert g["kind"] == "global-buffer-overflow" and g["elements_past_end"] == 1
    s = parsers.parse_asan(ASAN_STACKOVF)
    assert s["kind"] == "stack-overflow"
    assert parsers.looks_like_stack_overflow(None, s, None)


def test_asan_none():
    assert parsers.parse_asan("hello") is None and parsers.parse_asan("") is None


def test_ubsan_dedup_and_kinds():
    r = parsers.parse_ubsan(UBSAN)
    kinds = [x["kind"] for x in r]
    assert kinds == ["signed-integer-overflow", "index-out-of-bounds", "division-by-zero"]
    assert r[1]["elements_past_end"] == 0 and r[1]["bound"] == 10


def test_valgrind_uninit():
    r = parsers.parse_valgrind(VG)
    assert r["uninit"] and r["error_count"] == 5
    assert r["kinds"]["uninit-cond"]["line"] == 4
    assert parsers.parse_valgrind("")["ran"] is False


def test_gcc_filters_headers():
    r = parsers.parse_compiler_output(GCC, "main.cpp")
    assert r["count_by_flag"] == {"-Wparentheses": 1, "-Wmaybe-uninitialized": 1}
    assert r["errors"][0]["line"] == 9


def test_compare_statuses():
    assert compare_output("6\n", "6")["status"] == "pass"
    assert compare_output("1\n2\n", "1 2\n")["status"] == "presentation"
    w = compare_output("1 2 4\n", "1 2 3\n")
    assert w["status"] == "wrong" and w["prefix_tokens"] == 2 and w["numeric_deltas"] == [1]
    assert compare_output("", "5\n")["empty_output"]
    assert compare_output("3 2 1", "1 2 3")["reversed_tokens"]
    assert compare_output("1 2", "1 2 3")["is_prefix_of_expected"]


def test_docker_argv_has_isolation_flags():
    from sandbox_runner import RunConfig
    from sandbox_runner.docker_backend import docker_argv
    argv = docker_argv("img@sha256:abc", "/tmp/job", RunConfig())
    joined = " ".join(argv)
    for flag in ("--network none", "--read-only", "--pids-limit 64", "--user 65534:65534",
                 "--cap-drop ALL", "--cpus 1"):
        assert flag in joined
    assert "img@sha256:abc" in argv


def test_config_fingerprint_ignores_speed_options():
    from sandbox_runner import RunConfig
    assert RunConfig(use_pch=True).fingerprint() == RunConfig(use_pch=False).fingerprint()
    assert RunConfig().fingerprint() != RunConfig(double_run=False).fingerprint()


def test_pick_skips_large_inputs_for_slow_passes():
    from sandbox_runner.runner import _pick
    res = [{"idx": 0, "status": "pass"}, {"idx": 1, "status": "wrong"}, {"idx": 2, "status": "timeout"}]
    sizes = [10, 500_000, 20]
    assert _pick(res, "first_failing", sizes, 1000) == [2]
    assert _pick(res, "all", sizes, 1000) == [0, 2]
    assert _pick(res, "failing", [9e9, 9e9, 5e9], 1000) == [2]  # all too big -> smallest kept
    assert _pick(res, "first_failing") == [1]  # no limit -> unchanged behaviour


def test_pick_can_skip_timeouts():
    from sandbox_runner.runner import _pick
    res = [{"idx": 0, "status": "timeout"}, {"idx": 1, "status": "wrong"}, {"idx": 2, "status": "pass"}]
    assert _pick(res, "first_failing", skip_timeouts=True) == [1]
    assert _pick([{"idx": 0, "status": "timeout"}], "first_failing", skip_timeouts=True) == []
    assert _pick(res, "all", skip_timeouts=True) == [1, 2]
