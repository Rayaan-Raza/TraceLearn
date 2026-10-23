# CI/CD pipeline

TraceLearn uses two GitHub Actions workflows. Both are in `.github/workflows/`.

> **NOTE:** This document uses ASD-STE100 Simplified Technical English.

## 1. CI (`ci.yml`)

CI starts on each push to `main`, on each pull request, and from the **Actions** tab.

| Job | What it does |
|-----|--------------|
| `backend` | Installs `g++` and `bubblewrap`. Checks that the sandbox operates. Runs `pytest backend/tests` on Python 3.11 and 3.12. Uploads the JUnit report as the `pytest-report-<version>` artifact. |
| `frontend` | Runs `npm ci`, `npm run lint` (oxlint) and `npm run build` (TypeScript check and Vite build) on Node 22. |

A failed job makes the commit or the pull request red. Do not merge a pull request that has a red check.

> **NOTE:** Ubuntu 24.04 blocks unprivileged user namespaces. bubblewrap must have them. The `backend` job sets `kernel.apparmor_restrict_unprivileged_userns=0` for this reason.

## 2. CD (`cd.yml`)

CD starts when you push a tag that starts with `v`, or from the **Actions** tab.

| Job | What it does |
|-----|--------------|
| `ci` | Runs all of `ci.yml` again on the tagged commit. |
| `build` | Builds the frontend. Writes `BUILD_INFO.json` (version, commit SHA, build time, workflow run). Makes the frontend bundle, the backend bundle and `SHA256SUMS`. Uploads them as the `release-bundle` artifact. |
| `smoke` | Unpacks the backend bundle. Starts it with `APP_ENV=production` and bubblewrap. Checks `/health`. Compiles and runs problem `CP01` in the sandbox. Checks that the bundle commit is the tagged commit. |
| `release` | Tags only. Publishes the bundle as a GitHub Release. |

The frontend bundle contains `build-info.json`. Open `https://<frontend address>/build-info.json` to see the commit of a deployed frontend.

## 3. Make a release

1. Make sure that CI is green on `main`.
2. Make a tag and push it:

   ```
   git tag -a v0.1.0-mid -m "FYP-1 mid evaluation build"
   git push origin v0.1.0-mid
   ```

3. Open the **Actions** tab and wait for the `CD` run to complete.
4. Open **Releases**. Download the bundle or record the commit SHA in the evaluation worksheet.

## 4. Deploy a release

The CD workflow does not copy the bundle to a server. It has no server address and no credentials.

- **Backend:** On the Linux server, unpack `tracelearn-backend-<version>.tar.gz`. Then do the steps in README section 27.1.
- **Frontend:** Vercel builds the frontend from the repository (README section 27.2). Alternatively, upload the contents of `tracelearn-frontend-<version>.tar.gz` to a static host.

## 5. Recommended repository settings

An owner of the repository must set these items in **Settings → Branches**:

- Protect `main`.
- Require a pull request before a merge.
- Require the status checks `Backend tests (Python 3.11)`, `Backend tests (Python 3.12)` and `Frontend lint and build`.
