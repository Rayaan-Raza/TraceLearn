from pathlib import Path
ROOT = Path(r"c:/Users/rayaan/Desktop/POC")

def w(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")

w("frontend/src/api.ts", """const BASE = '';
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
""")

w("frontend/src/App.tsx", r"""import { useEffect, useState } from 'react';
import Editor from '@monaco-editor/react';
import { api, Problem, ProblemDetail, RunResult, Student } from './api';

const TABS = ['Submission', 'Evidence', 'Compare', 'Timeline', 'Teacher/Experiment'] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Submission');
  const [students, setStudents] = useState<Student[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [studentId, setStudentId] = useState<number>(1);
  const [problemId, setProblemId] = useState('P01');
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [code, setCode] = useState('');
  const [result, setResult] = useState<RunResult | null>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [comparison, setComparison] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Student[]>('/api/students').then(setStudents).catch(console.error);
    api<Problem[]>('/api/problems').then(setProblems).catch(console.error);
    api<any>('/api/evaluation/comparison').then(setComparison).catch(() => {});
  }, []);

  useEffect(() => {
    api<ProblemDetail>(`/api/problems/${problemId}`).then((p) => { setProblem(p); setCode(p.starter_code); }).catch(console.error);
  }, [problemId]);

  useEffect(() => {
    api<any[]>(`/api/students/${studentId}/timeline`).then(setTimeline).catch(() => setTimeline([]));
    api<any>(`/api/students/${studentId}/learner-profile`).then(setProfile).catch(() => setProfile(null));
  }, [studentId, result]);

  async function runAndAnalyze() {
    setLoading(true); setError('');
    try {
      const sub = await api<any>('/api/submissions', { method: 'POST', body: JSON.stringify({ student_id: studentId, problem_id: problemId, source_code: code }) });
      const r = await api<RunResult>(`/api/submissions/${sub.id}/run-and-analyze`, { method: 'POST' });
      setResult(r);
      setEvidence(await api<any[]>(`/api/submissions/${sub.id}/evidence`));
      setComparison(await api('/api/evaluation/comparison'));
    } catch (e: any) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }

  const historyChanged = !!(result?.current_only && result?.history_aware &&
    (result.current_only.primary_misconception !== result.history_aware.primary_misconception ||
      Math.abs(result.current_only.primary_confidence - result.history_aware.primary_confidence) > 0.05));

  const groups = ['execution', 'test', 'static', 'sequence', 'history', 'context'];

  return (
    <div className="app">
      <h1>TraceLearn POC</h1>
      <div className="tabs">{TABS.map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      {error && <div className="highlight">{error}</div>}
      {tab === 'Submission' && (
        <div className="panel">
          <div className="row">
            <label>Student<select value={studentId} onChange={(e) => setStudentId(Number(e.target.value))}>{students.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}</select></label>
            <label>Problem<select value={problemId} onChange={(e) => setProblemId(e.target.value)}>{problems.map((p) => <option key={p.id} value={p.id}>{p.id}: {p.title}</option>)}</select></label>
            <button onClick={runAndAnalyze} disabled={loading}>{loading ? 'Running...' : 'Run & Analyze'}</button>
          </div>
          {problem && <p>{problem.description}</p>}
          <div className="grid2">
            <Editor height="450px" language="python" value={code} onChange={(v) => setCode(v || '')} options={{ lineNumbers: 'on', fontSize: 14, minimap: { enabled: false } }} />
            <div>
              {result && (<>
                <p><span className="badge">{result.execution_status}</span> runtime: {result.runtime_ms?.toFixed(1) ?? '-'} ms</p>
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
      {tab === 'Evidence' && (
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
      {tab === 'Compare' && (
        <div className="panel grid2">
          <div><h3>Current submission only</h3><pre>{JSON.stringify(result?.current_only, null, 2)}</pre></div>
          <div><h3>With learner history</h3><pre>{JSON.stringify(result?.history_aware, null, 2)}</pre>{historyChanged && <div className="highlight">History changed the result</div>}</div>
        </div>
      )}
      {tab === 'Timeline' && (
        <div className="panel">
          <h2>Learner Timeline — {profile?.display_name}</h2>
          {profile?.learner_states?.map((ls: any) => <p key={ls.id}><span className="badge">{ls.misconception_id}</span> {ls.state} ({ls.confidence.toFixed(2)})</p>)}
          {timeline.map((t) => (
            <div key={t.submission_id} style={{ marginBottom: 12 }}>
              <strong>{t.problem_id} attempt {t.attempt_number}</strong> → {t.primary_diagnosis || '-'}
              {t.state_transitions?.map((tr: any, i: number) => <div key={i}>↳ {tr.old_state} → {tr.new_state}</div>)}
            </div>
          ))}
        </div>
      )}
      {tab === 'Teacher/Experiment' && (
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
  const [msg, setMsg] = useState('');
  async function review(action: string) {
    await api('/api/diagnoses/' + diagnosisId + '/teacher-review', { method: 'POST', body: JSON.stringify({ action }) });
    setMsg('Review saved: ' + action);
  }
  return <div><h3>Teacher review</h3><button onClick={() => review('CONFIRM')}>Confirm</button> <button onClick={() => review('REJECT')}>Reject</button> <button onClick={() => review('CORRECT')}>Correct</button> <button onClick={() => review('MARK_UNCERTAIN')}>Mark uncertain</button>{msg && <p>{msg}</p>}</div>;
}
""")

print('frontend src ok')
