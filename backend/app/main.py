import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.app.api.auth import router as auth_router
from backend.app.api.bank import router as bank_router
from backend.app.api.classrooms import router as classrooms_router
from backend.app.api.demo import router as demo_router
from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.learners import router as learners_router
from backend.app.api.problems import router as problems_router
from backend.app.api.students import router as students_router
from backend.app.api.submissions import router as submissions_router
from backend.app.api.teachers import router as teachers_router
from backend.app.auth.dependencies import CSRF_HEADER
from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.execution.sandbox import sandbox_status
from backend.app.security.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware

log = logging.getLogger("tracelearn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = settings.validate_for_startup()
    if problems:
        raise RuntimeError("Refusing to start with insecure configuration:\n- " + "\n- ".join(problems))
    init_db()
    status = sandbox_status()
    if not status["isolated"]:
        msg = "Code execution sandbox: bubblewrap NOT available; running with resource limits only."
        if status["required"]:
            log.error(msg + " Execution requests will be refused (REQUIRE_SANDBOX is on).")
        else:
            log.warning(msg + " Do not expose this server to untrusted users.")
    yield


app = FastAPI(
    title="TraceLearn POC",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# Order matters: the last added middleware runs first.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in settings.cors_origins if o != "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", CSRF_HEADER],
    max_age=600,
)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)

for r in (
    auth_router, bank_router, problems_router, students_router, submissions_router, learners_router,
    teachers_router, evaluation_router, demo_router, classrooms_router,
):
    app.include_router(r, prefix="/api")


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Return field-level messages without echoing the submitted values back.
    errors = [
        {"loc": [str(p) for p in e.get("loc", [])][-3:], "msg": str(e.get("msg", ""))[:200]}
        for e in exc.errors()[:20]
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Optional: serve the built SPA from the same origin (SERVE_FRONTEND=true).
# Same-origin deployment keeps cookies first-party and CSRF surface minimal.
# --------------------------------------------------------------------------
if settings.serve_frontend:
    dist = settings.frontend_dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"SERVE_FRONTEND is on but {index} does not exist. Run `npm run build` in frontend/.")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / full_path).resolve()
        # Path traversal guard: only files inside dist are served.
        if full_path and dist in candidate.parents and candidate.is_file():
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in f"/{full_path}" else {}
            return FileResponse(candidate, headers=headers)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
