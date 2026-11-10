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
