from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import Student
from pydantic import BaseModel

router = APIRouter(prefix="/students", tags=["students"])

class StudentRead(BaseModel):
    id: int
    display_name: str
    is_synthetic: bool
    model_config = {"from_attributes": True}

@router.get("", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[Student]:
    return db.query(Student).order_by(Student.id).all()
