# TraceLearn intermediate data

This folder holds parsed tables produced by the ingestion adapter.

Every file here is generated. Do not edit any file by hand.

Re-run the adapter to change the content.

---

## Layout

| Folder | Contents |
|---|---|
| `normalized/problems/` | Problem statements and sample tests. |
| `normalized/submissions/` | Source submissions and outcomes. |
| `normalized/exclusions/` | Refused records with reason codes. |

Read `normalized/README.md` for the schema and the run manifest.

---

## Regenerate

```bash
python scripts/ingest_sources.py --with-submissions
```

The first CodeNet C++ run takes about 45 minutes. Later runs reuse the hash cache and finish in seconds.

Use a smaller run for quick checks.

```bash
python scripts/ingest_sources.py --sources codestream --limit 500
```

---

## Rules

1. Delete this folder only when you plan to regenerate it.
2. Keep the hash cache. It saves about 45 minutes per run.
3. Quote the ingestion run id when you use these tables.
4. Report counts from the manifest. Do not count rows by hand.
