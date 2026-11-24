# Coordinator notes (not for raters)

Groups: {'disputed': 105, 'control_other': 20, 'control_class': 15}. Classes of the edit in the disputed group: {'UNINITIALIZED_VAR': 1, 'LOOP_BOUNDARY': 22, 'OFF_BY_ONE': 73, 'INT_OVERFLOW': 9}. The disputed rows
are most of the sheet, so controls only partly hide which rows they are. Anyone who has read
docs/WEAK_CLASS_STRATEGY.md or the pull request is not a blind rater.

After every rater has submitted, adjudicate with `evidence.md` and `key.csv`. An edit that breaks
passing tests is weak evidence. Report agreement on the controls too. Record decisions in
`annotations/label_review_decisions.jsonl` (action `relabel` or `confirm`, basis `human`, item_id,
signed_off_by, note); never edit labels in place.
