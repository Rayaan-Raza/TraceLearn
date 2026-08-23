from pydantic import BaseModel

class EvidenceItemRead(BaseModel):
    id: int
    submission_id: int
    source_type: str
    evidence_code: str
    misconception_id: str | None = None
    direction: str
    weight: float
    description: str
    details_json: str = "{}"
    model_config = {"from_attributes": True}
