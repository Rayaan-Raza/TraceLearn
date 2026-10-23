# TraceLearn data

This tree holds generated data only.

Raw datasets live in `G:\TraceLearn\Datasets_RAW`. That folder is read-only.

Do not commit large raw archives to Git.

---

## Layout

| Folder | Contents |
|---|---|
| `intermediate/` | Parsed and normalized tables. |
| `intermediate/normalized/problems/` | One row per problem statement. |
| `intermediate/normalized/submissions/` | One row per source submission. |
| `intermediate/normalized/exclusions/` | One row per refused record. |

---

## Planned folders

The Master Plan section 4 defines more folders. Create them when the matching stage exists.

| Folder | Stage |
|---|---|
| `raw/` | Gitignored raw archives. Not used yet. |
| `intermediate/filtered/` | After C++ filtering. |
| `intermediate/deduplicated/` | After duplicate detection. |
| `processed/features/` | After feature extraction. |
| `processed/annotations/` | After human review. |
| `processed/splits/` | Frozen train, validation and test splits. |
| `synthetic/` | Generated C++ examples. |
| `manifests/` | Source register and file checksums. |
| `reports/` | Ingestion and quality reports. |

Do not create an empty folder. Create it when real files belong in it.

---

## Rules

1. Treat `Datasets_RAW` as read-only.
2. Generate tables with scripts. Never edit them by hand.
3. Keep synthetic data separate from real learner data.
4. Record a release id with every published table.
5. Verify dataset licences before redistributing any file.
