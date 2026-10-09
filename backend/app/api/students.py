from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import false, or_
from sqlalchemy.orm import Session

from backend.app.auth.access import teacher_student_ids
from backend.app.auth.dependencies import require_teacher
from backend.app.db.database import get_db
from backend.app.db.models import Student, User

router = APIRouter(prefix="/students", tags=["students"])


class StudentRead(BaseModel):
    id: int
    display_name: str
    is_synthetic: bool
    model_config = {"from_attributes": True}


@router.get("", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db), teacher: User = Depends(require_teacher)) -> list[Student]:
    """Students the teacher may see: their classroom members + synthetic research students."""
    ids = teacher_student_ids(db, teacher)
    q = db.query(Student).filter(or_(Student.is_synthetic.is_(True), Student.id.in_(ids) if ids else false()))
    return q.order_by(Student.is_synthetic, Student.display_name, Student.id).all()
