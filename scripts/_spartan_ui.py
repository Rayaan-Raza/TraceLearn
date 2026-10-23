from pathlib import Path

CSS = r"""/* TraceLearn POC - intentionally spartan. Not production UI. */
:root { font-family: Georgia, "Times New Roman", serif; font-size: 15px; line-height: 1.4; color: #000; background: #fff; }
* { box-sizing: border-box; }
body { margin: 0; }
.app { max-width: 960px; margin: 0 auto; padding: 12px 16px 24px; }
.app > h1 { font-size: 1.25rem; font-weight: normal; margin: 0 0 4px; }
.poc-label { font-size: 0.85rem; color: #444; margin: 0 0 12px; font-style: italic; }
.tabs { display: flex; flex-wrap: wrap; margin-bottom: 16px; border-bottom: 1px solid #000; }
.tabs button { border: 1px solid #000; border-bottom: none; background: #fff; color: #000; padding: 4px 10px; margin-right: -1px; cursor: pointer; font: inherit; border-radius: 0; }
.tabs button.active { background: #eee; font-weight: bold; }
.screen-header h2 { font-size: 1.1rem; font-weight: bold; margin: 0 0 4px; }
.muted { color: #444; font-size: 0.9rem; }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; margin: 12px 0; }
.toolbar label { display: block; font-size: 0.9rem; }
select, button, input, textarea { font: inherit; padding: 2px 4px; border: 1px solid #000; background: #fff; border-radius: 0; }
button.primary { background: #fff; font-weight: normal; }
button.primary:disabled { color: #888; cursor: not-allowed; }
.problem-description, .card, .results-pane, .editor-pane { border: 1px solid #000; padding: 8px; margin-bottom: 12px; background: #fff; }
.description-body { white-space: pre-wrap; margin: 0; font-family: inherit; }
.submission-layout { display: grid; grid-template-columns: 1fr 280px; gap: 12px; align-items: start; }
@media (max-width: 800px) { .submission-layout { grid-template-columns: 1fr; } }
.results-pane pre, pre { background: #f5f5f5; color: #000; border: 1px solid #ccc; padding: 6px; overflow: auto; font-size: 12px; font-family: "Courier New", Courier, monospace; border-radius: 0; max-height: 160px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th, .data-table td { border: 1px solid #000; padding: 4px 6px; text-align: left; }
.comparison-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.comparison-grid.history-changed .compare-col:last-child { outline: 2px solid #000; outline-offset: 2px; }
.banner { border: 1px solid #000; padding: 6px 8px; margin: 8px 0; background: #f5f5f5; }
.banner.highlight { background: #eee; font-weight: bold; }
.pill, .tag, .badge { display: inline; font-size: inherit; padding: 0; border-radius: 0; background: none; margin: 0; }
.pill::before, .tag::before { content: "["; } .pill::after, .tag::after { content: "]"; }
.hint-card { background: #fff; }
.timeline { list-style: decimal; padding-left: 1.5rem; margin: 0; }
.timeline-item { padding: 4px 0; }
.timeline-item time { display: block; font-size: 0.85rem; color: #444; }
.misconception { font-weight: bold; }
.evidence-group li { border-top: 1px solid #ccc; padding: 4px 0; }
.review-list { list-style: square; padding-left: 1.25rem; }
"""

Path("frontend/src/index.css").write_text(CSS, encoding="utf-8")
app = Path("frontend/src/App.tsx")
text = app.read_text(encoding="utf-8")
if "poc-label" not in text:
    text = text.replace(
        "<h1>TraceLearn POC</h1>",
        '<h1>TraceLearn POC</h1>\n        <p className="poc-label">Research prototype — UI intentionally minimal.</p>',
    )
    app.write_text(text, encoding="utf-8")
Path("frontend/src/styles.css").write_text("/* consolidated in index.css */\n", encoding="utf-8")
print("spartan css applied")
