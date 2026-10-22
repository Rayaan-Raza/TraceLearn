"""
tests/test_lane_a.py — Lane A synthetic data pipeline tests.

Covers:
  1. JSONL schema validation (all §6 required fields present and typed)
  2. Operator library integrity (must-fire / must-not-fire fixtures)
  3. Collision check correctness
  4. E5 mislabel audit (sample-based, <10% threshold)
"""
import json
import re
import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL_PATH = os.path.join(REPO_ROOT, "annotations", "tier0_mutants.jsonl")
OPR_PATH = os.path.join(REPO_ROOT, "scripts", "operator_library.json")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def rows():
    with open(JSONL_PATH, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


@pytest.fixture(scope="module")
def operator_lib():
    with open(OPR_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# §6 Schema tests
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = [
    "row_id", "dataset_source", "source_record_id", "problem_id",
    "problem_cluster", "language", "label", "label_source",
    "label_confidence", "secondary_labels", "verdict",
    "firing_functions", "seed_ref", "mutation_op",
    "verified_by_execution", "taxonomy_version", "schema_version",
]

VALID_CLASSES = {
    "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS",
    "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE",
    "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK",
    "CPP_STALE_EXIT", "CPP_OTHER_ERROR",
}


def test_jsonl_required_fields(rows):
    """Every row must contain all §6 required fields."""
    for row in rows:
        missing = [f for f in REQUIRED_FIELDS if f not in row]
        assert not missing, f"row {row.get('row_id')} missing fields: {missing}"


def test_jsonl_label_values(rows):
    """Every label must be a valid tl-cpp-v2 class."""
    for row in rows:
        assert row["label"] in VALID_CLASSES, (
            f"row {row['row_id']} has invalid label '{row['label']}'"
        )


def test_jsonl_label_source(rows):
    """label_source must be 'synthetic' for all Lane A rows."""
    for row in rows:
        assert row["label_source"] == "synthetic", (
            f"row {row['row_id']} label_source={row['label_source']}"
        )


def test_jsonl_verified_by_execution(rows):
    """verified_by_execution must be True (boolean) for every row."""
    for row in rows:
        assert row["verified_by_execution"] is True, (
            f"row {row['row_id']} verified_by_execution={row['verified_by_execution']!r}"
        )


def test_jsonl_taxonomy_version(rows):
    """taxonomy_version must be 'tl-cpp-v2'."""
    for row in rows:
        assert row["taxonomy_version"] == "tl-cpp-v2", (
            f"row {row['row_id']} taxonomy_version={row['taxonomy_version']}"
        )


def test_jsonl_schema_version(rows):
    """schema_version must be '1.0'."""
    for row in rows:
        assert row["schema_version"] == "1.0", (
            f"row {row['row_id']} schema_version={row['schema_version']}"
        )


def test_jsonl_no_duplicate_row_ids(rows):
    """row_id must be unique across the entire file."""
    ids = [r["row_id"] for r in rows]
    dupes = [id_ for id_ in ids if ids.count(id_) > 1]
    assert not dupes, f"duplicate row_ids: {set(dupes)}"


def test_jsonl_language(rows):
    """language field must be 'cpp'."""
    for row in rows:
        assert row.get("language") == "cpp", (
            f"row {row['row_id']} language={row.get('language')}"
        )


# ---------------------------------------------------------------------------
# Operator library tests
# ---------------------------------------------------------------------------

def test_operator_lib_structure(operator_lib):
    """operator_library.json must have required top-level keys."""
    for key in ("version", "operators", "decoy_operators"):
        assert key in operator_lib, f"operator_library missing key '{key}'"


def test_operator_lib_all_classes_present(operator_lib):
    """All 11 tl-cpp-v2 classes (except OTHER_ERROR) need an operators entry."""
    taxonomy_classes = VALID_CLASSES - {"CPP_OTHER_ERROR"}
    for cls in taxonomy_classes:
        assert cls in operator_lib["operators"], (
            f"operator_library missing class '{cls}'"
        )


def test_operator_forms_have_pattern_and_replacement(operator_lib):
    """Every operator form must have a non-empty pattern and replacement."""
    for cls, entry in operator_lib["operators"].items():
        for form in entry.get("forms", []):
            assert form.get("pattern"), f"{cls}/{form.get('name')} missing pattern"
            assert form.get("replacement") is not None, (
                f"{cls}/{form.get('name')} missing replacement"
            )


def test_operator_patterns_compile(operator_lib):
    """Every operator pattern must be a valid Python regex."""
    for cls, entry in operator_lib["operators"].items():
        for form in entry.get("forms", []):
            pat = form.get("pattern", "")
            try:
                re.compile(pat, re.MULTILINE | re.DOTALL)
            except re.error as exc:
                pytest.fail(f"{cls}/{form['name']} bad regex: {exc}")
    for form in operator_lib.get("decoy_operators", []):
        pat = form.get("pattern", "")
        try:
            re.compile(pat, re.MULTILINE | re.DOTALL)
        except re.error as exc:
            pytest.fail(f"decoy/{form['name']} bad regex: {exc}")


# ---------------------------------------------------------------------------
# Must-fire / must-not-fire operator fixtures
# ---------------------------------------------------------------------------

MUST_FIRE_CASES = [
    # (class, op_name, seed_snippet, expected_substring_in_mutant)
    ("CPP_LOOP_BOUNDARY",     "lb_le_to_lt",
     "for(int i=1;i<=n;i++) s+=i;",
     "i<n"),
    ("CPP_OFF_BY_ONE",        "obo_index_plus1",
     "sum += arr[i + 1];",     # operator removes the +1 (reverse mutation)
     "arr[i]"),
    ("CPP_UNINITIALIZED_VAR", "uninit_int_zero",
     "int cnt = 0;",
     "int cnt;"),
    ("CPP_INT_OVERFLOW",      "overflow_ll_sum_to_int",
     "long long sum = 0;",
     "int sum"),
    ("CPP_INT_OVERFLOW",      "overflow_remove_ll_cast",
     "long long r = (long long)a * b;",
     "a * b"),
    ("CPP_INT_OVERFLOW",      "overflow_1ll_removed",
     "long long p = 1LL * n * m;",
     "n * m"),
    ("CPP_MISSING_BASE_CASE", "mbc_remove_base_n0",
     "if(n == 0) { return 1; }",
     ""),   # removed entirely
    ("CPP_ASSIGN_VS_COMPARE", "avc_eq_to_assign_if",
     "if(x == target) cnt++;",   # pattern requires simple \w+ identifiers
     "if(x = target)"),
    ("CPP_WRONG_LOOP_DIR",    "wld_lt_to_gt",
     "for(int i=0;i<n;i++)",
     "i>n"),
    ("CPP_ARRAY_BOUNDS",      "ab_vector_init_minus1",
     "vector<int> buf(n);",
     "buf(n-1)"),
    ("CPP_ARRAY_BOUNDS",      "ab_vector_at_oob",
     "buf.at(n-1)",
     "buf.at(n)"),
]

MUST_NOT_FIRE_CASES = [
    # (class, op_name, seed_snippet_that_should_not_match)
    ("CPP_LOOP_BOUNDARY",     "lb_le_to_lt",           "for(int i=0;i<n;i++)"),
    ("CPP_OFF_BY_ONE",        "obo_index_plus1",        "sum += val;"),
    ("CPP_UNINITIALIZED_VAR", "uninit_int_zero",        "int cnt = 1;"),
    ("CPP_INT_OVERFLOW",      "overflow_ll_sum_to_int", "long long counter = 0;"),
    ("CPP_ARRAY_BOUNDS",      "ab_vector_init_minus1",  "int arr[n];"),
    ("CPP_ARRAY_BOUNDS",      "ab_vector_at_oob",       "buf.at(i)"),
]


def _get_form(operator_lib, cls, op_name):
    if cls == "CPP_OTHER_ERROR":
        forms = operator_lib.get("decoy_operators", [])
    else:
        forms = operator_lib.get("operators", {}).get(cls, {}).get("forms", [])
    matches = [f for f in forms if f["name"] == op_name]
    assert matches, f"operator not found: {cls}/{op_name}"
    return matches[0]


@pytest.mark.parametrize("cls,op_name,seed,expected", MUST_FIRE_CASES)
def test_operator_must_fire(operator_lib, cls, op_name, seed, expected):
    """Operator must transform a matching seed snippet."""
    form = _get_form(operator_lib, cls, op_name)
    if form["replacement"] == "__callable__":
        pytest.skip("callable form — tested separately")
    pat = re.compile(form["pattern"], re.MULTILINE | re.DOTALL)
    result = pat.sub(form["replacement"], seed, count=1)
    assert result != seed, (
        f"{cls}/{op_name} pattern did not match seed: {seed!r}"
    )
    if expected:
        assert expected in result, (
            f"{cls}/{op_name} expected {expected!r} in result {result!r}"
        )


@pytest.mark.parametrize("cls,op_name,seed", MUST_NOT_FIRE_CASES)
def test_operator_must_not_fire(operator_lib, cls, op_name, seed):
    """Operator must NOT match a seed that does not have the target pattern."""
    form = _get_form(operator_lib, cls, op_name)
    if form["replacement"] == "__callable__":
        pytest.skip("callable form — tested separately")
    pat = re.compile(form["pattern"], re.MULTILINE | re.DOTALL)
    result = pat.sub(form["replacement"], seed, count=1)
    assert result == seed, (
        f"{cls}/{op_name} incorrectly fired on: {seed!r} → {result!r}"
    )


# ---------------------------------------------------------------------------
# Collision check tests
# ---------------------------------------------------------------------------

def test_collision_check_import():
    """generate_mutants collision check function must be importable."""
    import generate_mutants
    assert hasattr(generate_mutants, "check_collision")


def test_collision_check_no_false_positives():
    """Patterns already present in the seed must not trigger a collision."""
    import generate_mutants
    seed = "for(int i=1;i<=n;i++) s+=i;"
    mutant = "for(int i=1;i<n;i++) s+=i;"    # LB mutation
    collisions = generate_mutants.check_collision(seed, mutant, "CPP_LOOP_BOUNDARY")
    assert collisions == [], (
        f"False-positive collision for LB mutation: {collisions}"
    )


def test_collision_check_detects_new_pattern():
    """A mutant that NEWLY introduces a pattern from another class triggers collision."""
    import generate_mutants
    seed = "for(int i=0;i<n;i++) arr[i]=i;"
    mutant = "for(int i=0;i<n;i++) arr[i + 1]=i;"   # adds OBO pattern to an LB seed
    collisions = generate_mutants.check_collision(seed, mutant, "CPP_LOOP_BOUNDARY")
    assert "CPP_OFF_BY_ONE" in collisions, (
        f"Expected OBO collision, got: {collisions}"
    )


# ---------------------------------------------------------------------------
# E5 Mislabel audit (sample-based)
# ---------------------------------------------------------------------------

OPERATOR_PREFIX_MAP = {
    "CPP_LOOP_BOUNDARY":    ("lb_",),
    "CPP_OFF_BY_ONE":       ("obo_",),
    "CPP_ARRAY_BOUNDS":     ("ab_",),
    "CPP_UNINITIALIZED_VAR":("uninit_",),
    "CPP_INT_OVERFLOW":     ("overflow_",),
    "CPP_MISSING_BASE_CASE":("mbc_",),
    "CPP_ASSIGN_VS_COMPARE":("avc_",),
    "CPP_WRONG_LOOP_DIR":   ("wld_",),
    "CPP_RANGE_CHECK":      ("rc_",),
    "CPP_STALE_EXIT":       ("se_",),
    "CPP_OTHER_ERROR":      ("decoy_",),
}


def test_e5_mislabel_rate_under_10_percent(rows):
    """E5 audit: operator prefix must match label for ≥90% of sampled rows."""
    import random
    rng = random.Random(42)
    sample = rng.sample(rows, min(50, len(rows)))
    mismatches = []
    for row in sample:
        lbl = row["label"]
        op = row.get("mutation_op", "")
        prefixes = OPERATOR_PREFIX_MAP.get(lbl, ())
        if prefixes and not any(op.startswith(p) for p in prefixes):
            mismatches.append((row["row_id"], lbl, op))
    rate = 100 * len(mismatches) / len(sample)
    assert rate < 10, (
        f"E5 mislabel rate {rate:.1f}% exceeds 10% threshold. "
        f"Mismatches: {mismatches}"
    )


def test_e5_all_classes_represented(rows):
    """At least 5 rows per class must be present (E3/E4 gate)."""
    from collections import Counter
    dist = Counter(r["label"] for r in rows)
    for cls in VALID_CLASSES:
        assert dist[cls] >= 5, (
            f"Class {cls} has only {dist[cls]} rows (need ≥5)"
        )
