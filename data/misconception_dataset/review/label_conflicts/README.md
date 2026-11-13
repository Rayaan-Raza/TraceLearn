# LB/OBO conflict queue

`lb_obo_conflicts.csv` is written by `python scripts/find_label_conflicts.py`: real rows labelled
LOOP_BOUNDARY or OFF_BY_ONE whose other-class repair makes every test pass. A person fills `relabel`
and `note` using section 6 of `../../ANNOTATION_GUIDELINE.md`; the merge applies signed decisions.
