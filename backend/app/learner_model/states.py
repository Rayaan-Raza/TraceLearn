from backend.app.db.models import MisconceptionState

INITIAL_STATE = MisconceptionState.NEW

def can_become_persistent(cross_problem_count: int, min_cross: int = 2) -> bool:
    return cross_problem_count >= min_cross
