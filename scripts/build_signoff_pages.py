"""Build a local, blind sign-off page for the model pre-review sheets.

    python scripts/build_signoff_pages.py --raw-root <Datasets_RAW> [--out DIR] [--all-rows]

Writes ``signoff.html`` (open it in any browser, no server, no Python needed).
For every row a person must sign it shows the problem statement, the student's
code and the execution evidence, and asks for **your own label first**. Only
after you commit to it does it reveal the current label and the model's label
and rationale (the anti-anchoring rule in ``review/model_prereview/README.md``).
If you change your label after the reveal, the page records that in
``human_notes``.

Rows shown, per sheet:
* weak-label sheets: the ``spotcheck = 1`` rows plus every gold row
  (dev_gold / test_iid in ``splits/splits.csv``);
* gold sheets (``dev_gold_*``, ``iid_test_*``): every row;
* ``--all-rows``: everything.

Progress is kept in the browser while you work. "Export" downloads each sheet as
a CSV with the human columns filled; bring it back with
``scripts/import_signoff.py``. The page contains student code, so it is written
to a git-ignored folder and must not be committed or published.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from prereview_common import COLUMNS, PREREVIEW_DIR, read_sheet  # noqa: E402

DS = ROOT / "data" / "misconception_dataset"
OUT_DIR = DS / "review" / "signoff_pages"
GOLD_SPLITS = {"dev_gold", "test_iid"}
PG_COPIES = ("progpedia", "progpedia (1)")
CLASSES = [
    ("CPP_LOOP_BOUNDARY", "The loop-test comparison operator is the cause (<= vs <, < n+1); fixing only the operator fixes every test."),
    ("CPP_OFF_BY_ONE", "Index/count arithmetic is off by one (a[i+1], start at 1, n vs n-1, array one slot short); the loop operator is right."),
    ("CPP_ARRAY_BOUNDS", "Out of bounds by more than one element, or a fixed array that is too small for the stated limits."),
    ("CPP_UNINITIALIZED_VAR", "A declared variable is read before it is given a value."),
    ("CPP_INT_OVERFLOW", "Arithmetic overflows its type and that causes the failure (typically only on large inputs)."),
    ("CPP_MISSING_BASE_CASE", "Recursion without a reachable stop; stack overflow growing with input size."),
    ("CPP_ASSIGN_VS_COMPARE", "= used where == was meant, inside a condition, and it changes the result."),
    ("CPP_WRONG_LOOP_DIR", "The loop runs in the wrong direction (reversed) where the task needs the other order."),
    ("CPP_RANGE_CHECK", "Input validation rejects valid input or accepts invalid input at a range boundary."),
    ("CPP_STALE_EXIT", "The loop's exit condition depends on a variable the loop never updates."),
    ("CPP_OTHER_ERROR", "A real failure that fits none of the classes above (logic error, wrong algorithm, debug output, bad exit status...)."),
]


def gold_row_ids(splits_csv: Path) -> set[str]:
    if not splits_csv.exists():
        return set()
    with open(splits_csv, newline="", encoding="utf-8") as f:
        return {r["row_id"] for r in csv.DictReader(f) if r["split"] in GOLD_SPLITS}


# Evidence keys that name or imply a class (the rule that fired, the execution
# lane's label, the repair operator). Shown only after the reviewer commits.
HINT_KEYS = {"lf", "repair", "partial_repair", "exec_decision", "exec_label"}


def split_evidence(evidence: dict) -> tuple[dict, dict]:
    """Flatten evidence into (observations shown up front, label hints shown after commit)."""
    obs, hints = {}, {}

    def walk(d: dict, prefix: str = "") -> None:
        for k, v in d.items():
            if isinstance(v, dict) and k != "sanitizer":
                walk(v, f"{prefix}{k}.")
            else:
                (hints if k in HINT_KEYS else obs)[f"{prefix}{k}"] = v

    walk(evidence)
    return obs, hints


def rows_to_sign(sheet_name: str, rows: list[dict], gold: set[str], all_rows: bool = False) -> list[dict]:
    """The rows a person must sign on this sheet (see module docstring)."""
    if all_rows or not sheet_name.startswith("weak_labels_"):
        return list(rows)
    return [r for r in rows if r.get("spotcheck") == "1" or (r.get("row_id") or "") in gold]


class CodeSource:
    """Looks up a sheet row's code and problem statement in the raw datasets."""

    def __init__(self, raw_root: Path | None):
        self.raw_root = raw_root
        self._cs = None

    def _codestream(self):
        if self._cs is None:
            from codestream_common import find_raw, load_problems, load_submissions
            raw = find_raw(str(self.raw_root))
            subs = load_submissions(raw)
            self._cs = ({s.submission_id: s for s in subs}, {s.source_submission_id: s for s in subs},
                        load_problems(raw))
        return self._cs

    def lookup(self, row: dict) -> dict:
        if self.raw_root is None:
            return {"code": None, "statement": None, "language": None}
        if row["dataset_source"] == "PROGPEDIA":
            rel = row["source_record_id"]
            num = rel.split("/")[0]
            code = statement = None
            for c in PG_COPIES:
                p = self.raw_root / c / rel
                if code is None and p.exists():
                    code = p.read_text(encoding="utf-8", errors="replace")
                st = self.raw_root / c / num / "statement.md"
                if statement is None and st.exists():
                    statement = st.read_text(encoding="utf-8", errors="replace")
            return {"code": code, "statement": statement, "language": "c" if rel.endswith(".c") else "cpp"}
        if row["dataset_source"] == "CODESTREAM":
            by_id, by_src, problems = self._codestream()
            s = by_id.get(row.get("submission_id") or "") or by_src.get(row.get("source_record_id") or "")
            if s is None:
                return {"code": None, "statement": None, "language": None}
            p = problems.get(s.problem_id)
            return {"code": s.code, "statement": p.statement if p else None, "language": s.language}
        return {"code": None, "statement": None, "language": None}


def build_payload(raw_root: Path | None, all_rows: bool = False, sheet_dir: Path = PREREVIEW_DIR,
                  splits_csv: Path = DS / "splits" / "splits.csv") -> dict:
    gold = gold_row_ids(splits_csv)
    src = CodeSource(raw_root)
    sheets = []
    for path in sorted(sheet_dir.glob("*.csv")):
        rows = read_sheet(path)
        todo = rows_to_sign(path.stem, rows, gold, all_rows)
        items = []
        for r in todo:
            looked = src.lookup(r)
            try:
                evidence = json.loads(r.get("evidence") or "{}")
            except ValueError:
                evidence = {"raw": r.get("evidence")}
            obs, hints = split_evidence(evidence if isinstance(evidence, dict) else {})
            items.append({"row": r, "gold": (r.get("row_id") or "") in gold or not path.stem.startswith("weak_labels_"),
                          "evidence": obs, "hints": hints, **looked})
        sheets.append({"name": path.stem, "file": path.name, "total_rows": len(rows), "items": items,
                       "all_rows": rows})
    return {"generated": dt.datetime.now().isoformat(timespec="seconds"), "columns": COLUMNS,
            "classes": [{"id": c, "def": d} for c, d in CLASSES], "sheets": sheets}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Label Sign-off</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e1dc;--accent:#2f5d8a;--ok:#2e7d4f;--bad:#a8402f;--warn:#9a6b00;--code:#f1f0ec}
@media (prefers-color-scheme:dark){:root{--bg:#171716;--fg:#ecebe6;--muted:#a3a29b;--card:#212120;--line:#353532;--accent:#7fa8d1;--ok:#6fbf8e;--bad:#e08a7a;--warn:#d8b25a;--code:#2a2a28}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{position:sticky;top:0;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;z-index:2}
header h1{font-size:16px;margin:0 8px 0 0}select,input,button,textarea{font:inherit;color:inherit}
select,input[type=text],textarea{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
button{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 12px;cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}button:disabled{opacity:.45;cursor:default}
main{max-width:1100px;margin:0 auto;padding:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
.meta{color:var(--muted);font-size:13px}.pill{display:inline-block;padding:1px 8px;border-radius:999px;border:1px solid var(--line);font-size:12px;margin-right:6px}
.gold{border-color:var(--warn);color:var(--warn)}pre{background:var(--code);border-radius:8px;padding:12px;overflow:auto;max-height:520px;font:13px/1.45 ui-monospace,Consolas,monospace;margin:8px 0}
pre .ln{color:var(--muted);user-select:none;display:inline-block;width:3.2em}
details summary{cursor:pointer;color:var(--accent)}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;margin:10px 0}
.choice{border:1px solid var(--line);border-radius:8px;padding:8px;cursor:pointer;font-size:13px}.choice b{display:block;font-size:13px}
.choice.sel{border-color:var(--accent);outline:2px solid var(--accent)}.reveal{border-left:4px solid var(--accent);padding:8px 12px;margin:10px 0;background:var(--bg);border-radius:6px}
.agree{color:var(--ok)}.disagree{color:var(--bad)}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.progress{height:6px;background:var(--line);border-radius:3px;flex:1;min-width:120px}.progress>div{height:100%;background:var(--ok);border-radius:3px}
.nav{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.nav button{padding:2px 8px;font-size:12px}.nav .done{border-color:var(--ok);color:var(--ok)}.nav .cur{outline:2px solid var(--accent)}
</style></head><body>
<header><h1>Label sign-off</h1>
<label>Sheet <select id="sheet"></select></label>
<label>Your name <input type="text" id="signer" size="18"></label>
<div class="progress" title="signed in this sheet"><div id="bar"></div></div><span id="count" class="meta"></span>
<button id="export" class="primary">Export this sheet (CSV)</button></header>
<main><div class="card meta" id="help">Judge each item from the statement, the code and the evidence. Pick <b>your own</b> label first; the current
and model labels appear only after you commit. Progress is saved in this browser; export each sheet when done and run
<code>scripts/import_signoff.py</code>. Do not share this file: it contains student code.</div>
<div class="nav" id="nav"></div><div id="item"></div></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const store={get(k){try{return JSON.parse(localStorage.getItem(k)||'null')}catch(e){return null}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const mem={};function load(k){return mem[k]!==undefined?mem[k]:(mem[k]=store.get(k))}function save(k,v){mem[k]=v;store.set(k,v)}
const sel=document.getElementById('sheet'),signer=document.getElementById('signer');
signer.value=load('signoff:signer')||'';signer.oninput=()=>save('signoff:signer',signer.value.trim());
D.sheets.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${s.name} (${s.items.length} to sign)`;sel.appendChild(o)});
let si=+(load('signoff:sheet')||0);if(si>=D.sheets.length)si=0;sel.value=si;let ii=0;
sel.onchange=()=>{si=+sel.value;ii=0;save('signoff:sheet',si);render()};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const key=(s,it)=>`signoff:${s.name}:${it.row.item_id}`;
function codeBlock(t){if(!t)return '<p class="meta">Code not found in the raw datasets for this row.</p>';
 return '<pre>'+t.split('\n').map((l,n)=>`<span class="ln">${n+1}</span>${esc(l)}`).join('\n')+'</pre>'}
function render(){const s=D.sheets[si];const nav=document.getElementById('nav');nav.innerHTML='';
 let done=0;s.items.forEach((it,n)=>{const st=load(key(s,it));if(st&&st.verdict)done++;const b=document.createElement('button');
  b.textContent=it.row.item_id;if(st&&st.verdict)b.className='done';if(n===ii)b.className+=' cur';b.onclick=()=>{ii=n;render()};nav.appendChild(b)});
 document.getElementById('bar').style.width=(s.items.length?100*done/s.items.length:0)+'%';
 document.getElementById('count').textContent=`${done} / ${s.items.length} signed`;
 const box=document.getElementById('item');if(!s.items.length){box.innerHTML='<div class="card">Nothing to sign on this sheet.</div>';return}
 const it=s.items[ii],r=it.row,st=load(key(s,it))||{};
 const fmt=o=>Object.entries(o||{}).filter(([k,v])=>v!==null&&v!==''&&!(Array.isArray(v)&&!v.length)).map(([k,v])=>`<div><b>${esc(k)}</b>: ${esc(typeof v==='object'?JSON.stringify(v):v)}</div>`).join('');
 let h=`<div class="card"><div class="row"><b>${esc(r.item_id)}</b><span class="pill">${esc(r.dataset_source)}</span><span class="pill">${esc(r.problem_id)}</span>${it.gold?'<span class="pill gold">gold: your signature decides</span>':''}${r.spotcheck==='1'?'<span class="pill">spot-check</span>':''}</div>
 <div class="meta">${esc(r.source_record_id||r.submission_id)} · ${esc(it.language||'')}</div>
 ${it.statement?`<details><summary>Problem statement</summary><pre>${esc(it.statement)}</pre></details>`:''}
 <h3>Code</h3>${codeBlock(it.code)}<h3>Execution evidence</h3><div class="meta">${fmt(it.evidence)||'none recorded'}</div></div>`;
 h+=`<div class="card"><h3>1. Your label</h3><div class="grid">${D.classes.map(c=>`<div class="choice ${st.own===c.id?'sel':''}" data-c="${c.id}"><b>${c.id.replace('CPP_','')}</b>${esc(c.def)}</div>`).join('')}
 <div class="choice ${st.own==='UNCERTAIN'?'sel':''}" data-c="UNCERTAIN"><b>UNCERTAIN</b>Cannot tell which class from the code and evidence.</div></div>
 <div class="row"><button id="commit" class="primary" ${st.own&&!st.revealed?'':'disabled'}>Commit and reveal</button><button id="unsure">Mark unsure (skip)</button></div></div>`;
 if(st.revealed){const agree=st.final===r.model_label;
  h+=`<div class="card"><h3>2. Compare</h3><div class="reveal">Current label: <b>${esc(r.current_label||'—')}</b> (${esc(r.current_label_source||'new item')}, ${esc(r.firing_functions||'')})<br>
  Model verdict: <b>${esc(r.model_verdict)}</b> → model label <b>${esc(r.model_label)}</b> (${esc(r.model_confidence)})<br><span class="meta">${esc(r.model_rationale)}</span>${fmt(it.hints)?`<div class="meta" style="margin-top:6px"><b>Rule / repair evidence:</b>${fmt(it.hints)}</div>`:''}</div>
  <p>Your committed label: <b>${esc(st.own)}</b>. Final label:
  <select id="final">${['UNCERTAIN',...D.classes.map(c=>c.id)].map(c=>`<option ${st.final===c?'selected':''}>${c}</option>`).join('')}</select>
  → <b class="${agree?'agree':'disagree'}">${agree?'agree with the model':'disagree with the model'}</b></p>
  <label>Notes <input type="text" id="notes" size="60" value="${esc(st.notes||'')}"></label>
  <div class="row" style="margin-top:10px"><button id="sign" class="primary">Sign</button>${st.verdict?`<span class="agree">signed: ${esc(st.verdict)} (${esc(st.at)})</span>`:''}</div></div>`}
 if(st.verdict==='unsure')h+=`<div class="card">Marked <b>unsure</b>; it counts neither way.</div>`;
 h+=`<div class="row"><button id="prev" ${ii?'':'disabled'}>← Previous</button><button id="next" ${ii<s.items.length-1?'':'disabled'}>Next →</button></div>`;
 box.innerHTML=h;
 box.querySelectorAll('.choice').forEach(el=>el.onclick=()=>{if(st.revealed)return;st.own=el.dataset.c;save(key(s,it),st);render()});
 const q=id=>document.getElementById(id);
 q('commit').onclick=()=>{st.revealed=true;st.final=st.own;save(key(s,it),st);render()};
 q('unsure').onclick=()=>{if(!needName())return;Object.assign(st,{verdict:'unsure',label:'',at:today(),by:signer.value.trim()});save(key(s,it),st);next()};
 if(q('final'))q('final').onchange=e=>{st.final=e.target.value;save(key(s,it),st);render()};
 if(q('notes'))q('notes').oninput=e=>{st.notes=e.target.value;save(key(s,it),st)};
 if(q('sign'))q('sign').onclick=()=>{if(!needName())return;const agree=st.final===r.model_label;
  Object.assign(st,{verdict:agree?'agree':'disagree',label:agree?'':st.final,at:today(),by:signer.value.trim()});save(key(s,it),st);next()};
 q('prev').onclick=()=>{ii--;render()};q('next').onclick=next;
 function next(){if(ii<s.items.length-1)ii++;render();window.scrollTo(0,0)}}
function needName(){if(signer.value.trim())return true;alert('Enter your name first.');signer.focus();return false}
function today(){return new Date().toISOString().slice(0,10)}
document.getElementById('export').onclick=()=>{const s=D.sheets[si];const byId={};s.items.forEach(it=>{const st=load(key(s,it));if(st&&st.verdict)byId[it.row.item_id]=st});
 const cols=D.columns;const q=v=>{v=String(v??'');return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
 const lines=[cols.join(',')];s.all_rows.forEach(r=>{const st=byId[r.item_id];const o={...r};
  if(st){let notes=st.notes||'';if(st.final&&st.own&&st.final!==st.own)notes=(notes?notes+' | ':'')+`label changed after reveal (first: ${st.own})`;
   Object.assign(o,{human_verdict:st.verdict,human_label:st.label||'',signed_off_by:st.by,signed_off_at:st.at,human_notes:notes})}
  lines.push(cols.map(c=>q(o[c])).join(','))});
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')+'\n'],{type:'text/csv'}));a.download=s.file;a.click()};
render();
</script></body></html>
"""


def render_page(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__DATA__", data)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-root", type=Path, default=None,
                    help="Datasets_RAW (CodeStream CSVs and progpedia/); without it the page has no code")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--all-rows", action="store_true")
    a = ap.parse_args(argv)
    payload = build_payload(a.raw_root, a.all_rows)
    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / "signoff.html"
    out.write_text(render_page(payload), encoding="utf-8")
    for s in payload["sheets"]:
        missing = sum(1 for it in s["items"] if not it["code"])
        print(f"{s['name']}: {len(s['items'])} to sign of {s['total_rows']}"
              + (f" ({missing} without code)" if missing else ""))
    print(f"-> {out}  (contains student code: keep it local, do not commit or share)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
