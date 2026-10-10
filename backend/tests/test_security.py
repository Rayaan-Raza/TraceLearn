"""Security regression tests: authentication, authorization (IDOR), CSRF,
input limits, rate limiting, information leakage and sandboxing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.tests.conftest import TEACHER_CODE, make_user

CPP_OK = '#include <iostream>\nint main(){int n; std::cin>>n; for(int i=1;i<=n;i++) std::cout<<i<<" "; return 0;}\n'


@pytest.fixture(scope="module")
def app_client(seeded_db):
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture
def world(seeded_db):
    """Teacher A with a classroom containing student S1; teacher B and student S2 outsiders."""
    ta, ta_data = make_user("teacher", "Teacher A")
    tb, _ = make_user("teacher", "Teacher B")
    s1, s1_data = make_user("student", "Ali")
    s2, s2_data = make_user("student", "Sara")
    room = ta.post("/api/classrooms", json={"code": "CS101", "name": "Intro"}).json()
    assert s1.post("/api/classrooms/join", json={"join_code": room["join_code"]}).status_code == 200
    prob = ta.post("/api/problems", json={
        "title": "Count to N", "topic": "Loops",
        "test_cases": [{"input": "3", "expected": "1 2 3"}, {"input": "5", "expected": "1 2 3 4 5", "visible": False}],
    }).json()
    return dict(ta=ta, tb=tb, s1=s1, s2=s2, s1_data=s1_data, s2_data=s2_data, room=room, prob=prob, ta_data=ta_data)


# ------------------------------------------------------------------ authentication
PROTECTED = [
    ("GET", "/api/problems"), ("GET", "/api/problems/P01"), ("GET", "/api/students"),
    ("POST", "/api/submissions"), ("GET", "/api/submissions/1"), ("POST", "/api/submissions/1/run-and-analyze"),
    ("GET", "/api/submissions/1/evidence"), ("GET", "/api/submissions/1/diagnoses"),
    ("GET", "/api/submissions/1/test-results"), ("GET", "/api/students/1/timeline"),
    ("GET", "/api/students/1/learner-profile"), ("GET", "/api/students/1/submissions"),
    ("POST", "/api/diagnoses/1/teacher-review"), ("GET", "/api/evaluation/comparison"),
    ("POST", "/api/demo/reset"), ("POST", "/api/demo/run-sequence/SYN001"),
    ("GET", "/api/classrooms"), ("POST", "/api/classrooms/join"), ("GET", "/api/assignments/mine"),
    ("GET", "/api/auth/me"), ("POST", "/api/auth/logout"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_endpoint_requires_auth(app_client, method, path):
    app_client.cookies.clear()
    r = app_client.request(method, path, json={})
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


def test_forged_and_tampered_tokens_rejected(app_client, seeded_db):
    from jose import jwt
    _, data = make_user("student")
    good = data["access_token"]
    forged = jwt.encode({"sub": str(data["user_id"]), "role": "teacher", "typ": "access"}, "wrong-secret", algorithm="HS256")
    header, payload, sig = good.split(".")
    for bad in (forged, f"{header}.{payload}.", "garbage", good[:-3] + "abc"):
        r = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401
    # alg=none must be refused
    none_tok = jwt.encode({"sub": str(data["user_id"])}, "", algorithm="HS256").split(".")
    r = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {none_tok[0]}.{none_tok[1]}."})
    assert r.status_code == 401


def test_logout_revokes_token(seeded_db):
    c, data = make_user("student")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_cannot_self_register_as_teacher(app_client):
    base = {"email": "evil@example.com", "password": "password123", "role": "teacher"}
    assert app_client.post("/api/auth/register", json=base).status_code == 403
    assert app_client.post("/api/auth/register", json={**base, "teacher_code": "nope"}).status_code == 403
    ok = app_client.post("/api/auth/register", json={**base, "teacher_code": TEACHER_CODE})
    assert ok.status_code == 201


def test_register_validation(app_client):
    assert app_client.post("/api/auth/register", json={"email": "x@example.com", "password": "short"}).status_code == 422
    assert app_client.post("/api/auth/register", json={"email": "not-an-email", "password": "longenough1"}).status_code == 422
    assert app_client.post("/api/auth/register", json={"email": "y@example.com", "password": "é" * 40}).status_code == 422  # > 72 bytes


def test_login_errors_do_not_reveal_accounts(app_client, seeded_db):
    _, data = make_user("student")
    wrong_pw = app_client.post("/api/auth/login", data={"username": data["email"], "password": "wrong-password"})
    no_user = app_client.post("/api/auth/login", data={"username": "ghost@example.com", "password": "wrong-password"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_login_rate_limited(app_client, seeded_db):
    _, data = make_user("student")
    codes = [app_client.post("/api/auth/login", data={"username": data["email"], "password": "bad-password"}).status_code for _ in range(15)]
    assert 429 in codes


# ------------------------------------------------------------------ cookie session + CSRF
def test_cookie_session_requires_csrf_for_writes(app_client, seeded_db):
    _, data = make_user("teacher")
    c = TestClient(app_client.app)
    r = c.post("/api/auth/login", data={"username": data["email"], "password": data["password"]})
    assert r.status_code == 200
    set_cookie = r.headers.get_list("set-cookie")
    session = next(h for h in set_cookie if h.startswith("tl_session="))
    assert "HttpOnly" in session and "SameSite=lax" in session
    assert c.get("/api/auth/me").status_code == 200  # reads work with cookie alone
    assert c.post("/api/classrooms", json={"code": "X", "name": "Y"}).status_code == 403  # no CSRF header
    bad = c.post("/api/classrooms", json={"code": "X", "name": "Y"}, headers={"X-CSRF-Token": "forged"})
    assert bad.status_code == 403
    good = c.post("/api/classrooms", json={"code": "X", "name": "Y"}, headers={"X-CSRF-Token": c.cookies.get("tl_csrf")})
    assert good.status_code == 201


# ------------------------------------------------------------------ authorization / IDOR
def test_student_cannot_submit_as_someone_else(world):
    r = world["s1"].post("/api/submissions", json={"problem_id": "P01", "source_code": "x", "student_id": world["s2_data"]["student_id"]})
    assert r.status_code == 403


def test_teachers_cannot_create_submissions(world):
    assert world["ta"].post("/api/submissions", json={"problem_id": "P01", "source_code": "x"}).status_code == 403


def test_submission_isolation(world):
    s1, s2, ta, tb = world["s1"], world["s2"], world["ta"], world["tb"]
    sub = s1.post("/api/submissions", json={"problem_id": "P05", "source_code": "def square_number(x):\n    return x*x\n"}).json()
    sid = sub["id"]
    assert s1.post(f"/api/submissions/{sid}/run-and-analyze").status_code == 200
    for path in ("", "/evidence", "/diagnoses", "/test-results", "/hints", "/reviews"):
        assert s2.get(f"/api/submissions/{sid}{path}").status_code == 404, path
        assert tb.get(f"/api/submissions/{sid}{path}").status_code == 404, path
        assert ta.get(f"/api/submissions/{sid}{path}").status_code == 200, path  # S1 is in A's class
    # Nobody but the owner can (re)execute it
    for c in (s2, ta, tb):
        assert c.post(f"/api/submissions/{sid}/run-and-analyze").status_code in (403, 404)
        assert c.post(f"/api/submissions/{sid}/next-hint").status_code in (403, 404)


def test_student_record_isolation(world):
    s1_id, s2_id = world["s1_data"]["student_id"], world["s2_data"]["student_id"]
    for path in ("timeline", "learner-profile", "submissions"):
        assert world["s1"].get(f"/api/students/{s1_id}/{path}").status_code == 200
        assert world["s1"].get(f"/api/students/{s2_id}/{path}").status_code == 404
        assert world["ta"].get(f"/api/students/{s1_id}/{path}").status_code == 200
        assert world["ta"].get(f"/api/students/{s2_id}/{path}").status_code == 404  # not in A's class
        assert world["tb"].get(f"/api/students/{s1_id}/{path}").status_code == 404
    assert world["s1"].get("/api/students").status_code == 403
    listed = {s["id"] for s in world["ta"].get("/api/students").json()}
    assert s1_id in listed and s2_id not in listed


def test_teacher_review_scoped_to_own_students(world):
    sub = world["s1"].post("/api/submissions", json={"problem_id": "P05", "source_code": "def square_number(x):\n    print(x*x)\n"}).json()
    res = world["s1"].post(f"/api/submissions/{sub['id']}/run-and-analyze").json()
    diag_id = res["history_aware"]["id"]
    body = {"action": "CONFIRM", "comment": "ok"}
    assert world["tb"].post(f"/api/diagnoses/{diag_id}/teacher-review", json=body).status_code == 404
    assert world["s1"].post(f"/api/diagnoses/{diag_id}/teacher-review", json=body).status_code == 403
    assert world["ta"].post(f"/api/diagnoses/{diag_id}/teacher-review", json=body).status_code == 200
    bad = world["ta"].post(f"/api/diagnoses/{diag_id}/teacher-review", json={"action": "CORRECT", "corrected_misconception": "DROP TABLE"})
    assert bad.status_code == 422


def test_classroom_isolation(world):
    rid = world["room"]["id"]
    assert world["tb"].get(f"/api/classrooms/{rid}").status_code == 404
    assert world["tb"].get(f"/api/classrooms/{rid}/overview").status_code == 404
    assert world["tb"].post(f"/api/classrooms/{rid}/assignments", json={"problem_id": "P01"}).status_code == 404
    assert world["s2"].get(f"/api/classrooms/{rid}").status_code == 404
    assert world["s1"].get(f"/api/classrooms/{rid}/overview").status_code == 403
    s1_view = world["s1"].get(f"/api/classrooms/{rid}").json()
    assert s1_view["join_code"] is None  # students never see the join code
    assert world["ta"].get(f"/api/classrooms/{rid}").json()["join_code"]


def test_custom_problem_visibility_and_assignment(world):
    pid, rid = world["prob"]["id"], world["room"]["id"]
    assert world["tb"].get(f"/api/problems/{pid}").status_code == 404
    assert world["s1"].get(f"/api/problems/{pid}").status_code == 404  # not assigned yet
    assert world["tb"].post(f"/api/classrooms/{rid}/assignments", json={"problem_id": pid}).status_code == 404
    # Teacher B cannot assign A's problem even to B's own class
    room_b = world["tb"].post("/api/classrooms", json={"code": "B", "name": "B"}).json()
    assert world["tb"].post(f"/api/classrooms/{room_b['id']}/assignments", json={"problem_id": pid}).status_code == 404
    # Cannot assign to non-members
    r = world["ta"].post(f"/api/classrooms/{rid}/assignments", json={"problem_id": pid, "student_ids": [world["s2_data"]["student_id"]]})
    assert r.status_code == 400
    a = world["ta"].post(f"/api/classrooms/{rid}/assignments", json={"problem_id": pid, "due_date": "Friday"}).json()
    detail = world["s1"].get(f"/api/problems/{pid}").json()
    hidden = [t for t in detail["test_cases"] if t["test_type"] == "hidden"]
    assert hidden and all(t["input_json"] is None and t["expected_output"] is None for t in hidden)
    assert world["s2"].get(f"/api/assignments/{a['id']}").status_code == 404
    assert world["s1"].patch(f"/api/assignments/{a['id']}", json={"state": "closed"}).status_code == 403
    assert world["tb"].patch(f"/api/assignments/{a['id']}", json={"state": "closed"}).status_code == 404


def test_research_endpoints_teacher_only(world):
    assert world["s1"].get("/api/evaluation/comparison").status_code == 403
    assert world["s1"].post("/api/demo/reset").status_code == 403
    assert world["s1"].post("/api/demo/run-sequence/SYN001").status_code == 403


def test_demo_path_injection_rejected(world):
    for bad in ("..%2F..%2Fetc%2Fpasswd", "SYN001.json", "x"):
        assert world["ta"].post(f"/api/demo/run-sequence/{bad}").status_code in (404, 422)


def test_demo_reset_keeps_real_users(world):
    assert world["ta"].post("/api/demo/reset").status_code == 200
    assert world["s1"].get("/api/auth/me").status_code == 200
    assert world["ta"].get(f"/api/classrooms/{world['room']['id']}").status_code == 200


# ------------------------------------------------------------------ leakage of hidden tests
def test_students_never_see_hidden_expected_outputs(world):
    s1 = world["s1"]
    sub = s1.post("/api/submissions", json={"problem_id": "P01", "source_code": "def sum_first_n(n):\n    return 0\n"}).json()
    res = s1.post(f"/api/submissions/{sub['id']}/run-and-analyze").json()
    non_visible = [t for t in res["test_results"] if t["test_type"] != "visible"]
    assert non_visible
    assert all(t["expected_output_json"] is None and t["actual_output_json"] is None for t in non_visible)
    stored = s1.get(f"/api/submissions/{sub['id']}/test-results").json()
    assert all(t["expected_output_json"] is None for t in stored if t["test_type"] != "visible")
    teacher_view = world["ta"].get(f"/api/submissions/{sub['id']}/test-results").json()
    assert any(t["expected_output_json"] is not None for t in teacher_view if t["test_type"] != "visible")


def test_ground_truth_never_exposed(world):
    import json as _json
    sub = world["s1"].post("/api/submissions", json={"problem_id": "P05", "source_code": "def square_number(x):\n    return x*x\n"}).json()
    blob = _json.dumps(world["s1"].get(f"/api/submissions/{sub['id']}").json())
    assert "ground_truth" not in blob


# ------------------------------------------------------------------ input limits
def test_oversized_source_rejected(world):
    big = "a" * (70 * 1024)
    r = world["s1"].post("/api/submissions", json={"problem_id": "P01", "source_code": big})
    assert r.status_code in (413, 422)


def test_request_body_cap(app_client):
    r = app_client.post("/api/auth/register", content=b"x" * (300 * 1024), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_validation_errors_do_not_echo_input(app_client):
    r = app_client.post("/api/auth/register", json={"email": "<script>alert(1)</script>", "password": "password123"})
    assert r.status_code == 422
    assert "<script>" not in r.text


def test_security_headers(app_client):
    r = app_client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_cors_rejects_unknown_origin(app_client):
    r = app_client.options("/api/auth/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


# ------------------------------------------------------------------ sandbox
def _assigned_cpp(world, code: str):
    pid, rid = world["prob"]["id"], world["room"]["id"]
    world["ta"].post(f"/api/classrooms/{rid}/assignments", json={"problem_id": pid})
    sub = world["s1"].post("/api/submissions", json={"problem_id": pid, "source_code": code}).json()
    return world["s1"].post(f"/api/submissions/{sub['id']}/run-and-analyze").json()


def test_cpp_correct_solution_passes(world):
    res = _assigned_cpp(world, CPP_OK)
    assert res["execution_status"] == "success", res
    assert all(t["passed"] for t in res["test_results"])


def test_cpp_include_of_host_file_blocked(world):
    for code in ('#include "/proc/self/environ"\nint main(){}', '#include </etc/passwd>\nint main(){}',
                 '#define F "/etc/passwd"\n#include F\nint main(){}', '%:include "/etc/passwd"\nint main(){}',
                 '#inc\\\nlude "/etc/passwd"\nint main(){}'):
        res = _assigned_cpp(world, code)
        assert res["execution_status"] == "syntax_error"
        assert "root:" not in res["stderr"] and "SECRET" not in res["stderr"]


def _bwrap() -> bool:
    from backend.app.execution.sandbox import bwrap_path
    return bwrap_path() is not None


@pytest.mark.skipif(not _bwrap(), reason="bubblewrap not installed")
def test_sandbox_blocks_files_network_and_env():
    from backend.app.execution.subprocess_runner import SubprocessExecutionRunner
    code = (
        "import os, socket\n"
        "def f():\n"
        "    out = {'env': sorted(os.environ)}\n"
        "    try:\n"
        "        open('/etc/passwd').read(); out['passwd'] = True\n"
        "    except OSError: out['passwd'] = False\n"
        "    try:\n"
        "        open(" + repr(str(__import__('pathlib').Path('README.md').resolve())) + ").read(); out['repo'] = True\n"
        "    except OSError: out['repo'] = False\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 80), 2); out['net'] = True\n"
        "    except OSError: out['net'] = False\n"
        "    return out\n"
    )
    res = SubprocessExecutionRunner().execute_function(code, "f", [], 5)
    assert res.status == "success", res
    v = res.return_value
    assert v["passwd"] is False and v["repo"] is False and v["net"] is False
    assert not any(k in v["env"] for k in ("SECRET_KEY", "TEACHER_SIGNUP_CODE", "DATABASE_URL"))


def test_sandbox_timeout_and_output_limits():
    from backend.app.execution.subprocess_runner import SubprocessExecutionRunner
    r = SubprocessExecutionRunner().execute_function("def f():\n    while True: pass\n", "f", [], 2)
    assert r.status == "timeout"
    r = SubprocessExecutionRunner().execute_function("def f():\n    x = 'a' * (2**33)\n    return 1\n", "f", [], 5)
    assert r.status == "runtime_error"


def test_python_runner_cannot_touch_server_process(seeded_db):
    """Student code must not run inside the API process (old runner exec'd in a fork)."""
    import os
    from backend.app.execution.sandbox import bwrap_path
    if not bwrap_path():
        # Without a PID namespace the child's parent *is* the server process.
        pytest.skip("needs the bubblewrap PID namespace")
    from backend.app.execution.subprocess_runner import SubprocessExecutionRunner
    r = SubprocessExecutionRunner().execute_function("import os\ndef f():\n    return os.getppid()\n", "f", [], 5)
    assert r.status == "success" and r.return_value != os.getpid()
