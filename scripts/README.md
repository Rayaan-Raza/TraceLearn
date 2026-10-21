# TraceLearn ingestion and audit scripts

These scripts read raw datasets and write normalized tables.

Run every script from the project root `G:\TraceLearn`.

---

## Scripts

### `ingest_sources.py`

Parses raw sources into normalized tables.

Version: `ingest_sources.py/1.1.0`

```bash
python scripts/ingest_sources.py
```

| Flag | Effect |
|---|---|
| `--sources` | Comma list: `codenet`, `codestream`, `progpedia`, or `all`. |
| `--with-submissions` | Walk the CodeNet C++ tree. Slower on first run. |
| `--inline-code` | Store source code inside each record. Increases file size. |
| `--limit` | Cap the number of submissions read. Use for smoke tests. |
| `--exclude-without-tests` | Drop problems that hold no sample tests. |
| `--outdir` | Output folder. Defaults to `data/intermediate/normalized`. |
| `--hash-cache` | SHA-256 cache file path for the CodeNet walk. |

Output goes to `data/intermediate/normalized`. Read the README in that folder for the schema.

### `audit_scan.py`

Reports file counts, sizes and extensions for every raw folder. Also samples CSV columns and language distributions.

```bash
python scripts/audit_scan.py
```

The script reads only. It writes nothing.

---

## Rules

1. Never write to `Datasets_RAW`. Treat that folder as read-only.
2. Record the parser version with every output.
3. Log every refused record with one reason code.
4. Keep raw source identifiers on every normalized record.
5. Re-run the script instead of editing output by hand.

---

## Adding a new source

1. Write one adapter function. Follow the pattern of `iter_codestream`.
2. Return a problem list and a submission list.
3. Build records with `base_problem` and `base_submission`.
4. Call `apply_outcome` when the source supplies a verdict.
5. Log every refused record through `log.add`.
6. Add the source to the `MISSING_SOURCES` list, then remove it after download.
7. Update the README in each output folder.
