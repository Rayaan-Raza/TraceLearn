from datetime import datetime
from pydantic import BaseModel, Field

class LearnerStateRead(BaseModel):
    id: int
    student_id: int
    misconception_id: str
    state: str
    confidence: float
    updated_at: datetime
    support_count: int = 0
    cross_problem_support_count: int = 0
    recent_success_count: int = 0
    model_config = {"from_attributes": True}

class TimelineEntry(BaseModel):
    submission_id: int
    problem_id: str
    attempt_number: int
    submitted_at: datetime
    execution_status: str | None = None
    primary_diagnosis: str | None = None
    state_transitions: list[dict] = Field(default_factory=list)

class LearnerProfile(BaseModel):
    student_id: int
    display_name: str
    is_synthetic: bool = False
    learner_states: list[LearnerStateRead] = Field(default_factory=list)
