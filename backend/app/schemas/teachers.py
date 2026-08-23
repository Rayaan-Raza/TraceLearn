from datetime import datetime
from pydantic import BaseModel

class TeacherReviewCreate(BaseModel):
    action: str
    corrected_misconception: str | None = None
    comment: str | None = None

class TeacherReviewRead(BaseModel):
    id: int
    submission_id: int
    diagnosis_id: int | None
    action: str
    corrected_misconception: str | None = None
    comment: str | None = None
    reviewed_at: datetime
    model_config = {"from_attributes": True}
