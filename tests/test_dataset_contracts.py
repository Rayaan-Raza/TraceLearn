"""R1 contract tests (master plan §6, §9.3-R1, §3).

Contracts under test:
- tracelearn_features.taxonomy: the tl-cpp-v2 label set (11 modeled, NO_MISCONCEPTION
  excluded), families, hard-3.
- data/misconception_dataset/label_mapping.csv: label catalog + operator->label rows
  (tier0 stores mutation_op; the merge derives the class by joining this file).
- data/misconception_dataset/features/label_defining_features.json: lf_inputs registry,
  every id referenced by label_mapping.csv must exist there.
- data/misconception_dataset/features/FEATURE_SCHEMA.md: feature table must enumerate
  exactly the registry (name+type set equality), full warning normalization map, and
  the tracelearn_features v0 interface signature.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from tracelearn_features import taxonomy
from tracelearn_features.schema import FEATURE_BLOCKS, feature_names

DATASET = Path(__file__).resolve().parents[1] / "data" / "misconception_dataset"
MAPPING_CSV = DATASET / "label_mapping.csv"
FEATURES_DIR = DATASET / "features"
SCHEMA_MD = FEATURES_DIR / "FEATURE_SCHEMA.md"
LF_JSON = FEATURES_DIR / "label_defining_features.json"

# ---------------------------------------------------------------- taxonomy


def test_taxonomy_version_and_counts():
    assert taxonomy.TAXONOMY_VERSION == "tl-cpp-v2"
    assert len(taxonomy.MODELED_LABELS) == 11
    assert taxonomy.NO_MISCONCEPTION not in taxonomy.MODELED_LABELS


def test_taxonomy_labels_match_master_plan_section_3_1():
    assert list(taxonomy.MODELED_LABELS) == [
        "CPP_LOOP_BOUNDARY",
        "CPP_OFF_BY_ONE",
        "CPP_ARRAY_BOUNDS",
        "CPP_UNINITIALIZED_VAR",
        "CPP_INT_OVERFLOW",
        "CPP_MISSING_BASE_CASE",
        "CPP_ASSIGN_VS_COMPARE",
        "CPP_WRONG_LOOP_DIR",
        "CPP_RANGE_CHECK",
        "CPP_STALE_EXIT",
        "CPP_OTHER_ERROR",
    ]


def test_families_match_section_3_1():
    assert taxonomy.FAMILY_OF == {
        "CPP_LOOP_BOUNDARY": "Boundary",
        "CPP_OFF_BY_ONE": "Boundary",
        "CPP_ARRAY_BOUNDS": "Boundary",
        "CPP_UNINITIALIZED_VAR": "Data",
        "CPP_INT_OVERFLOW": "Data",
        "CPP_MISSING_BASE_CASE": "ControlFlow",
        "CPP_WRONG_LOOP_DIR": "ControlFlow",
        "CPP_STALE_EXIT": "ControlFlow",
        "CPP_ASSIGN_VS_COMPARE": "Logic",
        "CPP_RANGE_CHECK": "Logic",
        "CPP_OTHER_ERROR": "Other",
    }
    assert taxonomy.HARD_3 == (
        "CPP_WRONG_LOOP_DIR",
        "CPP_RANGE_CHECK",
        "CPP_STALE_EXIT",
    )


def test_all_modeled_labels_have_families():
    missing = [l for l in taxonomy.MODELED_LABELS if l not in taxonomy.FAMILY_OF]
    assert missing == []


# ------------------------------------------------------------ label_mapping

@pytest.fixture(scope="module")
def mapping_rows() -> list[dict[str, str]]:
    with MAPPING_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_label_mapping_header_and_label_rows(mapping_rows):
    header = set(mapping_rows[0].keys())
    assert {
        "kind",
        "mutation_op",
        "label",
        "family",
        "modeled",
        "hard3",
        "status",
        "merged_into",
        "lf_inputs",
    } <= header
    label_rows = [r for r in mapping_rows if r["kind"] == "label"]
    assert {r["label"] for r in label_rows} == set(taxonomy.MODELED_LABELS) | {
        taxonomy.NO_MISCONCEPTION
    }


def test_label_mapping_families_agree_with_taxonomy(mapping_rows):
    for row in mapping_rows:
        if row["kind"] == "label":
            if row["label"] == taxonomy.NO_MISCONCEPTION:
                continue
            assert row["family"] == taxonomy.FAMILY_OF[row["label"]], row


def test_no_misconception_is_not_modeled(mapping_rows):
    row = next(
        r for r in mapping_rows if r["kind"] == "label" and r["label"] == taxonomy.NO_MISCONCEPTION
    )
    assert row["modeled"] == "no"
    assert row["status"] == "deterministic_branch"


def test_operator_rows_derive_labels_and_families(mapping_rows):
    ops = [r for r in mapping_rows if r["kind"] == "operator"]
    assert ops, "need at least the seed example operator from §6"
    labels = {r["label"] for r in mapping_rows if r["kind"] == "label"}
    for op in ops:
        assert op["label"] in labels, op
        assert op["family"] == taxonomy.FAMILY_OF[op["label"]], op
        assert op["mutation_op"], op
    # the §6 example row: mutation_op for_le_bound_lt_n1 -> CPP_LOOP_BOUNDARY
    example = next(r for r in ops if r["mutation_op"] == "for_le_bound_lt_n1")
    assert example["label"] == "CPP_LOOP_BOUNDARY"


def test_hard3_flagged(mapping_rows):
    hard3_labels = set(taxonomy.HARD_3)
    for row in mapping_rows:
        if row["kind"] == "label":
            expected = "yes" if row["label"] in hard3_labels else "no"
            assert row["hard3"] == expected, row


def test_merges_column_empty_before_g3(mapping_rows):
    # Pre-registered merges (G3f) execute later via this column; it ships empty.
    assert all(r["merged_into"] == "" for r in mapping_rows)


def test_lf_inputs_cover_the_pg_rules_and_discovery_detectors(mapping_rows):
    label_rows = {r["label"]: r for r in mapping_rows if r["kind"] == "label"}
    # §3.4 pg rules
    assert "pg-1" in label_rows["CPP_ASSIGN_VS_COMPARE"]["lf_inputs"]
    assert "pg-2" in label_rows["CPP_MISSING_BASE_CASE"]["lf_inputs"]
    assert "pg-3" in label_rows["CPP_ARRAY_BOUNDS"]["lf_inputs"]
    assert "pg-4" in label_rows["CPP_UNINITIALIZED_VAR"]["lf_inputs"]
    # §8: Umaima's weak floor is 0 for classes 4, 8, 9, 10 -> no "lf_weak"
    for label in (
        "CPP_UNINITIALIZED_VAR",
        "CPP_WRONG_LOOP_DIR",
        "CPP_RANGE_CHECK",
        "CPP_STALE_EXIT",
    ):
        assert "lf_weak" not in label_rows[label]["lf_inputs"], label
    # §13.5 discovery detectors
    assert "det-4" in label_rows["CPP_UNINITIALIZED_VAR"]["lf_inputs"]
    assert "det-8" in label_rows["CPP_WRONG_LOOP_DIR"]["lf_inputs"]
    assert "det-9" in label_rows["CPP_RANGE_CHECK"]["lf_inputs"]
    assert "det-10" in label_rows["CPP_STALE_EXIT"]["lf_inputs"]
    # §8: REAL OTHER_ERROR rows are human-confirmed only
    assert label_rows["CPP_OTHER_ERROR"]["lf_inputs"] == "synthetic_ops;human"


def test_no_forced_labels_uncertain_is_not_a_label(mapping_rows):
    assert not any(r["label"] == "UNCERTAIN" for r in mapping_rows)


# ------------------------------------------------- lf registry (lf_inputs)


@pytest.fixture(scope="module")
def lf_registry() -> dict:
    return json.loads(LF_JSON.read_text(encoding="utf-8"))


def test_registry_shape(lf_registry):
    assert lf_registry["schema_version"] == "1.0"
    assert lf_registry["taxonomy_version"] == "tl-cpp-v2"
    assert lf_registry["entries"]


def test_every_lf_input_id_in_mapping_has_a_registry_entry(mapping_rows, lf_registry):
    used: set[str] = set()
    for row in mapping_rows:
        if row["lf_inputs"]:
            used.update(x for x in row["lf_inputs"].split(";") if x)
    entries = lf_registry["entries"]
    assert used - set(entries) == set(), f"missing registry entries: {used - set(entries)}"


def test_registry_entries_reference_known_labels_and_features(lf_registry):
    all_features = set(feature_names())
    for key, entry in lf_registry["entries"].items():
        # Entries may be single-label ("label") or a group covering several
        # classes ("labels") — e.g. synthetic_ops spans the whole taxonomy.
        labels = entry.get("labels") or [entry.get("label")]
        assert all(lb in set(taxonomy.MODELED_LABELS) for lb in labels), key
        for feat in entry["features"]:
            assert feat in all_features, f"{key}: unknown feature {feat}"
        assert entry["confidence_cap"] in (0.55, 0.60, 0.85, 1.0), key
        assert entry["status"] in ("active", "pending", "candidate"), key


def test_pg_rule_caps_match_section_3_4(lf_registry):
    entries = lf_registry["entries"]
    assert entries["pg-1"]["confidence_cap"] == 0.60
    assert entries["pg-2"]["confidence_cap"] == 0.60
    assert entries["pg-3"]["confidence_cap"] == 0.60
    assert entries["pg-4"]["confidence_cap"] == 0.55


def test_discovery_detectors_are_candidates_never_labels(lf_registry):
    for key in ("det-4", "det-8", "det-9", "det-10"):
        entry = lf_registry["entries"][key]
        assert entry["status"] == "candidate", key
        assert entry["never_label_without_human"] is True, key


# ----------------------------------------------------------- FEATURE_SCHEMA


def test_schema_md_exists_and_pins_version():
    text = SCHEMA_MD.read_text(encoding="utf-8")
    assert "schema_version" in text
    assert re.search(r"schema_version.*\b1\.1\b", text)
    assert taxonomy.TAXONOMY_VERSION in text


def _md_feature_table(text: str) -> dict[str, str]:
    """Parse every registry row of the form | `block.name` | type | ..."""
    found: dict[str, str] = {}
    for match in re.finditer(r"^\|\s*`([a-z][a-z0-9_]*\.[a-z][a-z0-9_0-9]*)`\s*\|\s*(int|float|bool)\s*\|",
                             text, re.MULTILINE):
        name, ftype = match.group(1), match.group(2)
        assert name not in found, f"duplicate feature row in schema: {name}"
        found[name] = ftype
    return found


def test_feature_table_matches_registry_exactly():
    text = SCHEMA_MD.read_text(encoding="utf-8")
    md_features = _md_feature_table(text)
    code_features = {name: ftype for name, ftype in feature_names(with_types=True)}
    missing_in_md = set(code_features) - set(md_features)
    extra_in_md = set(md_features) - set(code_features)
    assert not missing_in_md, f"undocumented features: {sorted(missing_in_md)}"
    assert not extra_in_md, f"documented but not in registry: {sorted(extra_in_md)}"
    for name, ftype in code_features.items():
        assert md_features[name] == ftype, f"type mismatch for {name}"


def test_every_block_documented():
    text = SCHEMA_MD.read_text(encoding="utf-8")
    for block in FEATURE_BLOCKS:
        assert f"## `{block}`" in text or f"`{block}`" in text, block


def test_warning_normalization_map_is_complete():
    """The warning map table (canonical id -> -W flag) must cover every
    countable warning feature except the availability/total bookkeeping
    fields and the catch-all `other` bucket."""
    text = SCHEMA_MD.read_text(encoding="utf-8")
    md_ids = set(
        re.findall(
            r"^\|\s*`(warnings\.[a-z_0-9]+)`\s*\|\s*-W[a-z0-9-]+",
            text,
            re.MULTILINE,
        )
    )
    code_warning_ids = {
        n
        for n in feature_names()
        if n.startswith("warnings.")
    } - {"warnings.available", "warnings.total", "warnings.other"}
    assert md_ids == code_warning_ids, (
        f"md-only: {md_ids - code_warning_ids}, code-only: {code_warning_ids - md_ids}"
    )


def test_v0_interface_signature_documented():
    text = SCHEMA_MD.read_text(encoding="utf-8")
    assert "def extract_features(" in text
    assert "tracelearn_features" in text
    # lanes must be able to compute features from day one: signature shows blocks
    for block in ("warnings", "runtime", "tests", "cpg", "context"):
        assert f"{block}: " in text or f"{block}=" in text, block


def test_null_policy_documented():
    text = SCHEMA_MD.read_text(encoding="utf-8")
    assert "NaN" in text
    assert "meta" in text  # meta is never a feature
