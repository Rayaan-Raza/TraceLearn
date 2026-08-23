from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")
    print("w", rel)

# fixes
w("backend/app/learner_model/history.py", (ROOT/"backend/app/learner_model/history.py").read_text(encoding="utf-8").replace(
    "from backend.app.db.models import LearnerState, LearnerStateHistory, Problem, Submission, TestResult",
    "from backend.app.db.models import EvidenceItem, LearnerState, LearnerStateHistory, Problem, Submission, TestResult"
).replace("            from backend.app.db.models import EvidenceItem\n", ""))

w("backend/app/diagnosis/current_only.py", (ROOT/"backend/app/diagnosis/current_only.py").read_text(encoding="utf-8").replace(
    'from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, Submission, UncertaintyLevel',
    'from backend.app.db.models import Diagnosis, DiagnosisMode, EvidenceItem, EvidenceSourceType, Submission, UncertaintyLevel'
).replace(
    'q = q.filter(EvidenceItem.source_type != "history")',
    'q = q.filter(EvidenceItem.source_type != EvidenceSourceType.HISTORY)'
).replace(
    'if item.source_type.value == "history":',
    'if item.source_type == EvidenceSourceType.HISTORY:'
))

w("backend/app/execution/subprocess_runner.py", (ROOT/"backend/app/execution/subprocess_runner.py").read_text(encoding="utf-8") + "\n\nimport multiprocessing as _mp\nif __name__ == \"__main__\":\n    _mp.freeze_support()\n")

# Frontend scaffold
w("frontend/package.json", json.dumps({
    "name": "tracelearn-frontend",
    "private": True,
    "version": "0.1.0",
    "type": "module",
    "scripts": {"dev": "vite", "build": "tsc -b && vite build", "preview": "vite preview"},
    "dependencies": {"@monaco-editor/react": "^4.7.0", "react": "^19.0.0", "react-dom": "^19.0.0"},
    "devDependencies": {"@types/react": "^19.0.0", "@types/react-dom": "^19.0.0", "@vitejs/plugin-react": "^4.3.4", "typescript": "~5.7.2", "vite": "^6.0.0"}
}, indent=2))

import json

w("frontend/tsconfig.json", '{"files":[],"references":[{"path":"./tsconfig.app.json"},{"path":"./tsconfig.node.json"}]}')
w("frontend/tsconfig.app.json", '{"compilerOptions":{"target":"ES2020","useDefineForClassFields":true,"lib":["ES2020","DOM","DOM.Iterable"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"jsx":"react-jsx","strict":true,"noUnusedLocals":false,"noUnusedParameters":false,"noFallthroughCasesInSwitch":true,"noUncheckedSideEffectImports":true},"include":["src"]}')
w("frontend/tsconfig.node.json", '{"compilerOptions":{"target":"ES2022","lib":["ES2023"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"isolatedModules":true,"moduleDetection":"force","noEmit":true,"strict":true,"noUncheckedSideEffectImports":true},"include":["vite.config.ts"]}')
w("frontend/vite.config.ts", "import { defineConfig } from 'vite'\nimport react from '@vitejs/plugin-react'\nexport default defineConfig({ plugins: [react()], server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' } } })\n")
w("frontend/index.html", '<!doctype html><html lang="en"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>TraceLearn POC</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>')
w("frontend/src/main.tsx", "import { StrictMode } from 'react'\nimport { createRoot } from 'react-dom/client'\nimport App from './App'\nimport './styles.css'\ncreateRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)\n")
w("frontend/src/styles.css", "*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#f5f7fb;color:#1a1a2e}.app{max-width:1200px;margin:0 auto;padding:16px}.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}.tabs button{padding:8px 14px;border:1px solid #ccc;background:#fff;border-radius:6px;cursor:pointer}.tabs button.active{background:#2563eb;color:#fff;border-color:#2563eb}.panel{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:6px;overflow:auto;font-size:13px}.row{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap}select,button,input{padding:8px}.highlight{background:#fef3c7;padding:8px;border-radius:6px;margin-top:8px}.ev-group{margin-bottom:12px;border-top:1px solid #eee;padding-top:8px}.badge{display:inline-block;padding:2px 8px;border-radius:999px;background:#e0e7ff;font-size:12px;margin-right:6px}\n")

w("frontend/src/api.ts", '''
const BASE = '';
export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export type Problem = { id: string; title: string; function_name: string; concept_tags: string[] };
export type ProblemDetail = Problem & { description: string; starter_code: string };
export type Student = { id: number; display_name: string; is_synthetic: boolean };
export type RunResult = {
  submission_id: number; execution_status: string; runtime_ms?: number; stderr?: string;
  test_results: { test_case_id: string; passed: boolean; error_type?: string }[];
  evidence_count: number;
  current_only?: any; history_aware?: any; hint?: { level: number; text: string };
};
''')

w("frontend/src/App.tsx", '''
import { useEffect, useState } from "react";
import Editor from "@monaco-editor/react";
import { api, Problem, ProblemDetail, RunResult, Student } from "./api";

const TABS = ["Submission", "Evidence", "Compare", "Timeline", "Teacher/Experiment"] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Submission");
  const [students, setStudents] = useState<Student[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [studentId, setStudentId] = useState<number>(1);
  const [problemId, setProblemId] = useState("P01");
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [code, setCode] = useState("");
  const [result, setResult] = useState<RunResult | null>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [comparison, setComparison] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Student[]>("/api/students").then(setStudents).catch(console.error);
    api<Problem[]>("/api/problems").then(setProblems).catch(console.error);
    api<any>("/api/evaluation/comparison").then(setComparison).catch(() => {});
  }, []);

  useEffect(() => {
    api<ProblemDetail>(`/api/problems/${problemId}`).then((p) => { setProblem(p); setCode(p.starter_code); }).catch(console.error);
  }, [problemId]);

  useEffect(() => {
    api<any[]>(`/api/students/${studentId}/timeline`).then(setTimeline).catch(() => setTimeline([]));
    api<any>(`/api/students/${studentId}/learner-profile`).then(setProfile).catch(() => setProfile(null));
  }, [studentId, result]);

  async function runAndAnalyze() {
    setLoading(true); setError("");
    try {
      const sub = await api<any>("/api/submissions", { method: "POST", body: JSON.stringify({ student_id: studentId, problem_id: problemId, source_code: code }) });
      const r = await api<RunResult>(`/api/submissions/${sub.id}/run-and-analyze`, { method: "POST" });
      setResult(r);
      const ev = await api<any[]>(`/api/submissions/${sub.id}/evidence`);
      setEvidence(ev);
      setComparison(await api("/api/evaluation/comparison"));
    } catch (e: any) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }

  const historyChanged = result && result.current_only && result.history_aware &&
    (result.current_only.primary_misconception !== result.history_aware.primary_misconception ||
      Math.abs(result.current_only.primary_confidence - result.history_aware.primary_confidence) > 0.05);

  const groups = ["execution", "test", "static", "sequence", "history", "context"];

  return (
    <div className="app">
      <h1>TraceLearn POC</h1>
      <div className="tabs">{TABS.map((t) => <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}</div>
      {error && <div className="highlight">{error}</div>}

      {tab === "Submission" && (
        <div className="panel">
          <div className="row">
            <label>Student<select value={studentId} onChange={(e) => setStudentId(Number(e.target.value))}>{students.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}</select></label>
            <label>Problem<select value={problemId} onChange={(e) => setProblemId(e.target.value)}>{problems.map((p) => <option key={p.id} value={p.id}>{p.id}: {p.title}</option>)}</select></label>
            <button onClick={runAndAnalyze} disabled={loading}>{loading ? "Running..." : "Run & Analyze"}</button>
          </div>
          {problem && <p>{problem.description}</p>}
          <div className="grid2">
            <Editor height="450px" language="python" value={code} onChange={(v) => setCode(v || "")} options={{ lineNumbers: "on", fontSize: 14, minimap: { enabled: false } }} />
            <div>
              {result && (<>
                <p><span className="badge">{result.execution_status}</span> runtime: {result.runtime_ms?.toFixed(1) ?? "-"} ms</p>
                <h3>Test results</h3>
                <pre>{JSON.stringify(result.test_results, null, 2)}</pre>
                <h3>History-aware diagnosis</h3>
                <pre>{JSON.stringify(result.history_aware, null, 2)}</pre>
                {result.hint && <p><strong>Hint L{result.hint.level}:</strong> {result.hint.text}</p>}
              </>)}
            </div>
          </div>
        </div>
      )}

      {tab === "Evidence" && (
        <div className="panel">
          <h2>Evidence Inspector</h2>
          {groups.map((g) => {
            const items = evidence.filter((e) => e.source_type === g);
            if (!items.length) return null;
            return <div key={g} className="ev-group"><h3>{g}</h3>{items.map((it) => (
              <div key={it.id}><span className="badge">{it.direction}</span> {it.description} <em>({it.weight})</em> {it.misconception_id && <span className="badge">{it.misconception_id}</span>}</div>
            ))}</div>;
          })}
          {!evidence.length && <p>Run a submission to populate evidence.</p>}
        </div>
      )}

      {tab === "Compare" && (
        <div className="panel grid2">
          <div><h3>Current submission only</h3><pre>{JSON.stringify(result?.current_only, null, 2)}</pre></div>
          <div><h3>With learner history</h3><pre>{JSON.stringify(result?.history_aware, null, 2)}</pre>{historyChanged && <div className="highlight">History changed the result</div>}</div>
        </div>
      )}

      {tab === "Timeline" && (
        <div className="panel">
          <h2>Learner Timeline — {profile?.display_name}</h2>
          {profile?.learner_states?.map((ls: any) => <p key={ls.id}><span className="badge">{ls.misconception_id}</span> {ls.state} ({ls.confidence.toFixed(2)})</p>)}
          {timeline.map((t) => (
            <div key={t.submission_id} style={{ marginBottom: 12 }}>
              <strong>{t.problem_id} attempt {t.attempt_number}</strong> → {t.primary_diagnosis || "-"}
              {t.state_transitions?.map((tr: any, i: number) => <div key={i}>↳ {tr.old_state} → {tr.new_state}</div>)}
            </div>
          ))}
        </div>
      )}

      {tab === "Teacher/Experiment" && (
        <div className="panel">
          <h2>Experiment metrics</h2>
          <pre>{JSON.stringify(comparison, null, 2)}</pre>
          {result?.history_aware && <TeacherReview diagnosisId={result.history_aware.id} />}
        </div>
      )}
    </div>
  );
}

function TeacherReview({ diagnosisId }: { diagnosisId: number }) {
  const [msg, setMsg] = useState("");
  async function review(action: string) {
    await api("/api/diagnoses/" + diagnosisId + "/teacher-review", { method: "POST", body: JSON.stringify({ action }) });
    setMsg("Review saved: " + action);
  }
  return <div><h3>Teacher review</h3><button onClick={() => review("CONFIRM")}>Confirm</button> <button onClick={() => review("REJECT")}>Reject</button> <button onClick={() => review("CORRECT")}>Correct</button> <button onClick={() => review("MARK_UNCERTAIN")}>Mark uncertain</button>{msg && <p>{msg}</p>}</div>;
}
''')

w("frontend/src/vite-env.d.ts", '/// <reference types="vite/client" />\n')
print("frontend+fixes done")
