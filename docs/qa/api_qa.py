"""End-to-end API QA for TraceLearn Iteration 1. Run against a live backend."""
import json, sys, time, uuid
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CODE = "qa-teacher-code-2026"
RUN = uuid.uuid4().hex[:6]
results = []


def check(area, name, ok, detail=""):
    results.append((area, name, bool(ok), str(detail)[:300]))
    print(("PASS " if ok else "FAIL ") + f"[{area}] {name}" + (f"  -- {detail}" if not ok and detail else ""))


def client(token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.Client(base_url=BASE, headers=h, timeout=60)


anon = client()


def fresh():
    return httpx.Client(base_url=BASE, timeout=60)


def login(c, email, pw="Passw0rd!QA"):
    return c.post("/api/auth/login", data={"username": email, "password": pw})


def register(email, role="student", code=None, name="QA User"):
    body = {"email": email, "password": "Passw0rd!QA", "role": role, "display_name": name}
    if code:
        body["teacher_code"] = code
    return fresh().post("/api/auth/register", json=body)


# ---------------------------------------------------------------- RBAC / auth
r = register(f"t1_{RUN}@qa.test", "teacher", CODE, "Teacher One"); check("RBAC", "teacher registers with invite code", r.status_code == 201, r.text)
T1 = client(r.json()["access_token"])
r = register(f"t2_{RUN}@qa.test", "teacher", CODE, "Teacher Two"); T2 = client(r.json()["access_token"])
r = register(f"bad_{RUN}@qa.test", "teacher", None); check("RBAC", "teacher self-signup without code is refused", r.status_code == 403, r.status_code)
r = register(f"bad2_{RUN}@qa.test", "teacher", "wrong-code"); check("RBAC", "teacher signup with wrong code is refused", r.status_code == 403, r.status_code)
r = register(f"bad3_{RUN}@qa.test", "admin"); check("RBAC", "unknown role 'admin' is refused", r.status_code == 422, r.status_code)
r = register(f"sa_{RUN}@qa.test", "student", None, "Student A"); SA_ = r.json(); SA = client(SA_["access_token"])
r = register(f"sb_{RUN}@qa.test", "student", None, "Student B"); SB_ = r.json(); SB = client(SB_["access_token"])
r = register(f"sc_{RUN}@qa.test", "student", None, "Student C"); SC_ = r.json(); SC = client(SC_["access_token"])
r = register(f"sa_{RUN}@qa.test", "student"); check("RBAC", "duplicate email is refused", r.status_code == 409, r.status_code)
r = fresh().post("/api/auth/register", json={"email": f"x_{RUN}@qa.test", "password": "short", "role": "student"}); check("RBAC", "password < 8 chars is refused", r.status_code == 422, r.status_code)
r = login(fresh(), f"sa_{RUN}@qa.test", "wrong-password"); check("RBAC", "wrong password -> 401", r.status_code == 401, r.status_code)
r = login(fresh(), f"SA_{RUN}@QA.TEST"); check("RBAC", "login email is case-insensitive", r.status_code == 200, r.status_code)

for path in ["/api/auth/me", "/api/problems", "/api/students", "/api/classrooms", "/api/evaluation/comparison", "/api/bank/problems"]:
    r = fresh().get(path); check("RBAC", f"anonymous GET {path} -> 401", r.status_code == 401, r.status_code)
check("RBAC", "/health is public", anon.get("/health").status_code == 200)
r = client("not.a.jwt").get("/api/auth/me"); check("RBAC", "forged bearer token -> 401", r.status_code == 401, r.status_code)

check("RBAC", "student cannot list students", SA.get("/api/students").status_code == 403, SA.get("/api/students").status_code)
check("RBAC", "student cannot create classroom", SA.post("/api/classrooms", json={"code": "X", "name": "X"}).status_code == 403)
check("RBAC", "student cannot read evaluation metrics", SA.get("/api/evaluation/comparison").status_code == 403)
check("RBAC", "student cannot create problems", SA.post("/api/problems", json={}).status_code in (403, 422))
check("RBAC", "student cannot use demo endpoints", SA.post("/api/demo/reset").status_code == 403)
check("RBAC", "teacher cannot submit code", T1.post("/api/submissions", json={"problem_id": "CP01", "source_code": "int main(){}"}).status_code == 403)

r = T1.post("/api/classrooms", json={"code": f"CS{RUN}", "name": "QA Class"}); check("RBAC", "teacher creates classroom", r.status_code == 201, r.text)
cls = r.json(); join = cls.get("join_code")
r = SA.post("/api/classrooms/join", json={"join_code": join}); check("RBAC", "student A joins class with code", r.status_code == 200, r.text)
r = SB.post("/api/classrooms/join", json={"join_code": "WRONGCODE"}); check("RBAC", "wrong join code refused", r.status_code in (404, 400, 422), r.status_code)
check("RBAC", "teacher 2 cannot read teacher 1's class", T2.get(f"/api/classrooms/{cls['id']}").status_code == 404, T2.get(f"/api/classrooms/{cls['id']}").status_code)
check("RBAC", "student B (not member) cannot read the class", SB.get(f"/api/classrooms/{cls['id']}").status_code == 404)
check("RBAC", "member student cannot read class members", SA.get(f"/api/classrooms/{cls['id']}/members").status_code in (403, 404))

# CSRF with cookie session
ck = httpx.Client(base_url=BASE, timeout=30)
login(ck, f"t1_{RUN}@qa.test")
r = ck.post("/api/classrooms", json={"code": "CSRF", "name": "no token"}); check("RBAC", "cookie session without CSRF header -> 403", r.status_code == 403, r.status_code)
r = ck.post("/api/classrooms", json={"code": f"CK{RUN}", "name": "with token"}, headers={"X-CSRF-Token": ck.cookies.get("tl_csrf")}); check("RBAC", "cookie session with CSRF header works", r.status_code == 201, r.status_code)
sc = ck.cookies.get("tl_session") or ""
check("RBAC", "session cookie is HttpOnly", any("httponly" in h.lower() for h in login(fresh(), f"t1_{RUN}@qa.test").headers.get_list("set-cookie") if "tl_session" in h))

# ---------------------------------------------------------------- C++ execution pipeline
CORRECT = "#include <iostream>\nint main(){int n;std::cin>>n;long long s=0;for(int i=0;i<n;++i)s+=i;std::cout<<s<<'\\n';}"
OFF_BY_ONE = "#include <iostream>\nint main(){int n;std::cin>>n;long long s=0;for(int i=0;i<=n;++i)s+=i;std::cout<<s<<'\\n';}"


def submit(c, pid, src):
    r = c.post("/api/submissions", json={"problem_id": pid, "source_code": src})
    if r.status_code != 200:
        return r, None
    sid = r.json()["id"]
    return c.post(f"/api/submissions/{sid}/run-and-analyze"), sid


r, s_ok = submit(SA, "CP01", CORRECT); j = r.json()
check("C++ exec", "correct CP01 solution -> success, all tests pass", j.get("execution_status") == "success" and all(t["passed"] for t in j["test_results"]), j.get("execution_status"))
check("C++ exec", "visible + hidden tests are run", len(j.get("test_results", [])) >= 5, len(j.get("test_results", [])))
hidden = [t for t in j["test_results"] if t["test_type"] != "visible"]
check("C++ exec", "student never sees hidden test input/output", hidden and all(t["expected_output_json"] is None and t["actual_output_json"] is None for t in hidden))
check("C++ exec", "runtime_ms recorded", j.get("runtime_ms") is not None, j.get("runtime_ms"))

r, s_obo = submit(SA, "CP01", OFF_BY_ONE); j_obo = r.json()
check("C++ exec", "off-by-one -> some tests fail", j_obo.get("execution_status") is not None and not all(t["passed"] for t in j_obo["test_results"]), j_obo.get("execution_status"))

r, _ = submit(SB, "CP01", "#include <iostream>\nint main(){ std::cout << x; }"); j = r.json()
check("C++ exec", "compile error -> syntax_error with message", j.get("execution_status") == "syntax_error" and "error" in j.get("stderr", ""), (j.get("execution_status"), j.get("stderr", "")[:100]))
check("C++ exec", "compiler output does not leak server paths", "/tmp/" not in j.get("stderr", "") and "/home/" not in j.get("stderr", ""), j.get("stderr", "")[:200])

r, _ = submit(SB, "CP01", "#include <iostream>\nint main(){ volatile unsigned long long c=0; while(true){++c;} }"); j = r.json()
check("C++ exec", "infinite loop -> timeout", j.get("execution_status") == "timeout", j.get("execution_status"))

r, _ = submit(SB, "CP01", '#include "/etc/passwd"\nint main(){}'); j = r.json()
check("Sandbox", "#include of server file is refused", j.get("execution_status") == "syntax_error" and "standard" in j.get("stderr", "").lower(), j.get("stderr", "")[:120])

READ_ENV = r'''#include <fstream>
#include <iostream>
#include <string>
int main(){ const char* ps[]={"/home","/etc/passwd","/proc/1/environ","../.env","/root"}; for(auto p:ps){ std::ifstream f(p); std::string s; std::getline(f,s); std::cout<<p<<"="<<(f.good()?"OPEN:"+s.substr(0,20):"closed")<<"\n";} }'''
r, sid = submit(SB, "CP01", READ_ENV); j = r.json()
detail = T1.get(f"/api/submissions/{sid}/test-results")  # teacher not owner of SB -> should be 404
check("RBAC", "teacher cannot read a non-member student's submission", detail.status_code == 404, detail.status_code)
check("Sandbox", "file-read probe runs (status)", j.get("execution_status") in ("success", "wrong_answer", "runtime_error"), j.get("execution_status"))

r, _ = submit(SC, "CP01", "#include <iostream>\nint main(){ int* p=nullptr; std::cout<<*p; }"); j = r.json()
check("C++ exec", "null deref -> runtime_error", j.get("execution_status") == "runtime_error", j.get("execution_status"))

r = SC.post("/api/submissions", json={"problem_id": "CP01", "source_code": "x" * 70000}); check("C++ exec", "source > 64 KB refused", r.status_code in (413, 422), r.status_code)
r = SC.post("/api/submissions", json={"problem_id": "../../x", "source_code": "int main(){}"}); check("C++ exec", "invalid problem id refused", r.status_code == 422, r.status_code)
r = SC.post("/api/submissions", json={"problem_id": "ZZ99", "source_code": "int main(){}"}); check("C++ exec", "unknown problem -> 404", r.status_code == 404, r.status_code)
r = SC.post("/api/submissions", json={"problem_id": "CP01", "source_code": "int main(){}", "student_id": SA_["student_id"]}); check("RBAC", "cannot submit as another student", r.status_code == 403, r.status_code)

# ---------------------------------------------------------------- RBAC on submissions
check("RBAC", "student B cannot read student A's submission", SB.get(f"/api/submissions/{s_ok}").status_code == 404)
check("RBAC", "student B cannot read A's evidence", SB.get(f"/api/submissions/{s_obo}/evidence").status_code == 404)
check("RBAC", "student B cannot run A's submission", SB.post(f"/api/submissions/{s_ok}/run-and-analyze").status_code == 404)
check("RBAC", "student B cannot read A's learner profile", SB.get(f"/api/students/{SA_['student_id']}/learner-profile").status_code in (403, 404))
check("RBAC", "teacher 1 (A's teacher) can read A's submission", T1.get(f"/api/submissions/{s_obo}").status_code == 200)
check("RBAC", "teacher 2 (not A's teacher) cannot read A's submission", T2.get(f"/api/submissions/{s_obo}").status_code == 404)
tr = T1.get(f"/api/submissions/{s_obo}/test-results").json()
check("RBAC", "teacher sees hidden test data", any(t["test_type"] != "visible" and t["expected_output_json"] is not None for t in tr))
stud = T1.get("/api/students").json()
ids = {s["id"] for s in stud}
check("RBAC", "teacher's student list contains own member A", SA_["student_id"] in ids, ids)
check("RBAC", "teacher's student list excludes non-member B", SB_["student_id"] not in ids, ids)

# ---------------------------------------------------------------- Evidence + diagnosis
ev = SA.get(f"/api/submissions/{s_obo}/evidence").json()
codes = [e.get("evidence_code") for e in ev]
check("Evidence", "off-by-one submission produced evidence items", len(ev) > 0, len(ev))
check("Evidence", "evidence items carry source/code/direction/weight", ev and all(k in ev[0] for k in ("source_type", "evidence_code", "direction", "weight")), list(ev[0].keys()) if ev else None)
check("Evidence", "loop-boundary evidence found for `<=`", any("LOOP" in (c or "") or "BOUND" in (c or "") or "M01" in (c or "") for c in codes), codes)
dg = SA.get(f"/api/submissions/{s_obo}/diagnoses").json()
modes = {d.get("mode") for d in dg}
check("Evidence", "both current_only and history_aware diagnoses exist", {"current_only", "history_aware"} <= modes, modes)
prim = [d.get("primary_misconception") or d.get("primary") for d in dg]
check("Taxonomy", "off-by-one diagnosed as a loop-boundary misconception", any(p and ("M01" in p or "LOOP" in p or "OFF_BY_ONE" in p) for p in prim), json.dumps(dg)[:300])
conf = [d.get("confidence") for d in dg]
check("Evidence", "confidence values are within [0,1]", all(c is None or 0 <= c <= 1 for c in conf), conf)
check("Evidence", "no ground-truth fields in student diagnoses", "ground_truth" not in json.dumps(dg).lower())
ev_ok = SA.get(f"/api/submissions/{s_ok}/diagnoses").json()
check("Taxonomy", "correct solution -> NO_MISCONCEPTION", all((d.get("primary_misconception") or "") in ("NO_MISCONCEPTION", "") or d.get("primary_misconception") is None for d in ev_ok), json.dumps(ev_ok)[:300])

# ---------------------------------------------------------------- Submission logging
subs = SA.get(f"/api/students/{SA_['student_id']}/submissions").json()
mine = [s for s in subs if s["problem_id"] == "CP01"]
check("Logging", "both of A's attempts are logged", len(mine) >= 2, len(mine))
check("Logging", "attempt numbers increase per problem", sorted(s["attempt_number"] for s in mine) == list(range(1, len(mine) + 1)), [s["attempt_number"] for s in mine])
one = SA.get(f"/api/submissions/{s_obo}").json()
check("Logging", "source code stored verbatim", one.get("source_code") == OFF_BY_ONE)
check("Logging", "submission has timestamp + status", one.get("submitted_at") and one.get("execution_status"), one)
check("Logging", "summary has tests_passed / tests_total", all("tests_passed" in s and "tests_total" in s for s in mine))
h = SA.post(f"/api/submissions/{s_obo}/next-hint"); check("Logging", "hint request works and is recorded", h.status_code == 200 and SA.get(f"/api/submissions/{s_obo}/hints").json(), h.text[:200])
dgt = T1.get(f"/api/submissions/{s_obo}/diagnoses").json()
did = dgt[0]["id"]
before = json.dumps(dgt)
r = T1.post(f"/api/diagnoses/{did}/teacher-review", json={"action": "CONFIRM", "comment": "QA"}); check("Logging", "teacher review saved", r.status_code in (200, 201), r.text[:200])
check("Logging", "teacher review does not alter original diagnosis", json.dumps(T1.get(f"/api/submissions/{s_obo}/diagnoses").json()) == before)
r = T2.post(f"/api/diagnoses/{did}/teacher-review", json={"action": "REJECT"}); check("RBAC", "other teacher cannot review A's diagnosis", r.status_code == 404, r.status_code)
r = SA.post(f"/api/diagnoses/{did}/teacher-review", json={"action": "REJECT"}); check("RBAC", "student cannot review own diagnosis", r.status_code == 403, r.status_code)
tl = SA.get(f"/api/students/{SA_['student_id']}/timeline"); check("Logging", "wrong-answer status is not labelled runtime_error", j_obo.get("execution_status") != "runtime_error", j_obo.get("execution_status"))
check("Logging", "learner timeline available", tl.status_code == 200, tl.status_code)

# logout invalidates tokens
tok = login(fresh(), f"sc_{RUN}@qa.test").json()["access_token"]
c = client(tok); c.post("/api/auth/logout")
check("RBAC", "logout revokes the token", c.get("/api/auth/me").status_code == 401)

passed = sum(1 for r in results if r[2])
print(f"\n{passed}/{len(results)} checks passed")
json.dump(results, open(sys.argv[2] if len(sys.argv) > 2 else "api_qa_results.json", "w"), indent=1)
