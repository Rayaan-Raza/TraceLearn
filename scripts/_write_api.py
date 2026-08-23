from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text(text.strip() + "\n", encoding="utf-8", newline="\n")

w("backend/app/api/problems.py", """
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import Problem, TestCase, TestVisibility
from backend.app.schemas.problems import ProblemDetail, ProblemSummary, TestCasePublic

router = APIRouter(prefix="/problems", tags=["problems"])


def _tags(raw: str) -> list[str]:
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


@router.get("", response_model=list[ProblemSummary])
def list_problems(db: Session = Depends(get_db)) -> list[ProblemSummary]:
    rows = db.query(Problem).order_by(Problem.id).all()
    return [
        ProblemSummary(
            id=p.id,
            title=p.title,
            difficulty=p.difficulty,
            taxonomy_tags=_tags(p.taxonomy_tags),
        )
        for p in rows
    ]


@router.get("/{problem_id}", response_model=ProblemDetail)
def get_problem(problem_id: str, db: Session = Depends(get_db)) -> ProblemDetail:
    problem = db.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem_id)
        .order_by(TestCase.sort_order)
        .all()
    )
    public_cases: list[TestCasePublic] = []
    for tc in cases:
        expected: str | None = tc.expected_stdout
        if tc.visibility in (TestVisibility.HIDDEN, TestVisibility.DIAGNOSTIC):
            expected = None
        public_cases.append(
            TestCasePublic(
                id=tc.id,
                name=tc.name,
                visibility=tc.visibility.value,
                sort_order=tc.sort_order,
                stdin=tc.stdin if tc.visibility == TestVisibility.VISIBLE else "",
                expected_stdout=expected if tc.visibility == TestVisibility.VISIBLE else None,
            )
        )

    return ProblemDetail(
        id=problem.id,
        title=problem.title,
        difficulty=problem.difficulty,
        taxonomy_tags=_tags(problem.taxonomy_tags),
        description=problem.description,
        starter_code=problem.starter_code,
        test_cases=public_cases,
    )
""")

w("backend/app/main.py", """
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.problems import router as problems_router
from backend.app.config import settings
from backend.app.db.database import init_db

app = FastAPI(title="TraceLearn POC", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(problems_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
""")

print("api+main ok")
