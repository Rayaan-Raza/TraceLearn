"""Tests for scripts/find_label_conflicts.py."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from find_label_conflicts import CONFLICT_PAIR, LB, OBO


class TestConflictPair:
    def test_pair_contains_lb_and_obo(self):
        assert LB in CONFLICT_PAIR
        assert OBO in CONFLICT_PAIR

    def test_pair_has_exactly_two_elements(self):
        assert len(CONFLICT_PAIR) == 2

    def test_lb_is_loop_boundary(self):
        assert LB == "CPP_LOOP_BOUNDARY"

    def test_obo_is_off_by_one(self):
        assert OBO == "CPP_OFF_BY_ONE"


class TestLoadAgentLabels:
    def test_returns_empty_dict_when_no_files(self, tmp_path, monkeypatch):
        from find_label_conflicts import load_agent_labels
        import find_label_conflicts as flc
        monkeypatch.setattr(flc, "DS", tmp_path)
        (tmp_path / "review" / "agent_labels").mkdir(parents=True)
        result = load_agent_labels()
        assert result == {}

    def test_loads_labels_from_jsonl(self, tmp_path, monkeypatch):
        from find_label_conflicts import load_agent_labels
        import find_label_conflicts as flc
        monkeypatch.setattr(flc, "DS", tmp_path)
        d = tmp_path / "review" / "agent_labels"
        d.mkdir(parents=True)
        (d / "batch1.jsonl").write_text(
            json.dumps({"row_id": "row-001", "label": LB}) + "\n"
            + json.dumps({"row_id": "row-001", "label": OBO}) + "\n"
            + json.dumps({"row_id": "row-002", "label": LB}) + "\n",
            encoding="utf-8",
        )
        result = load_agent_labels()
        assert result["row-001"] == [LB, OBO]
        assert result["row-002"] == [LB]


class TestRepairSignal:
    def test_lb_row_fixed_by_off_by_one_repair_is_a_conflict(self):
        from find_label_conflicts import conflict_signals
        s = conflict_signals(LB, {"repair.off_by_one_fix_all": "1", "repair.loop_boundary_fix_all": "0"}, [])
        assert s and s[0].startswith("repair:off_by_one_fix_all=1")

    def test_row_fixed_only_by_its_own_repair_is_not_a_conflict(self):
        from find_label_conflicts import conflict_signals
        assert conflict_signals(OBO, {"repair.off_by_one_fix_all": "1", "repair.loop_boundary_fix_all": "0"}, []) == []

    def test_other_labels_are_ignored(self):
        from find_label_conflicts import conflict_signals
        assert conflict_signals("CPP_ARRAY_BOUNDS", {"repair.off_by_one_fix_all": "1"}, [LB]) == []

    def test_synthetic_rows_are_skipped(self):
        from find_label_conflicts import find_conflicts
        labels = {"stu-1": {"label": LB, "dataset_source": "SYNTHETIC"},
                  "pgx-1": {"label": LB, "dataset_source": "PROGPEDIA", "problem_id": "p"}}
        feats = {k: {"repair.off_by_one_fix_all": "1"} for k in labels}
        assert [c["row_id"] for c in find_conflicts(labels, feats, {})] == ["pgx-1"]
