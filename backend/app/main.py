from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.auth import router as auth_router
from backend.app.api.demo import router as demo_router
from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.learners import router as learners_router
from backend.app.api.problems import router as problems_router
from backend.app.api.students import router as students_router
from backend.app.api.submissions import router as submissions_router
from backend.app.api.teachers import router as teachers_router
from backend.app.config import settings
from backend.app.db.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="TraceLearn POC", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(problems_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(submissions_router, prefix="/api")
app.include_router(learners_router, prefix="/api")
app.include_router(teachers_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(demo_router, prefix="/api")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
