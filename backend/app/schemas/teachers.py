from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.diagnosis.taxonomy import ALL_LABELS, CPP_MISCONCEPTIONS

VALID_LABELS = set(ALL_LABELS) | set(CPP_MISCONCEPTIONS)


class TeacherReviewCreate(BaseModel):
    action: Literal["CONFIRM", "REJECT", "CORRECT", "MARK_UNCERTAIN"]
    corrected_misconception: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check(self):
        if self.corrected_misconception is not None and self.corrected_misconception not in VALID_LABELS:
            raise ValueError("corrected_misconception must be a known misconception label")
        if self.action == "CORRECT" and not self.corrected_misconception:
            raise ValueError("CORRECT requires corrected_misconception")
        return self


class TeacherReviewRead(BaseModel):
    id: int
    submission_id: int
    diagnosis_id: int | None
    action: str
    corrected_misconception: str | None = None
    comment: str | None = None
    reviewed_at: datetime
    model_config = {"from_attributes": True}
