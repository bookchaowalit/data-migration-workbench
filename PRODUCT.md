# Migration Validation Workbench

Status as of 2026-10-23. Describes only what is in this repository today.

## Purpose

Check data after a migration: compare a legacy export with the new system's export and show
what matches, what is missing on either side, what is duplicated and which values differ,
with per-record evidence, human review and a reproducible audit package.

## Users

The owner, as a local tool and a demo for migration/data-quality engagements. No hosted users.

## What works

- Inputs: CSV/TSV, XLSX (bounded) and Parquet (optional `parquet` extra), converted to one
  canonical input contract with a SHA-256 fingerprint.
- Key selection, heuristic field-mapping suggestions, normalization profiles (`generic`,
  `thai_customer`: Thai names, phones, tax ids, dates, addresses; raw evidence untouched).
- Statuses `match`, `value_mismatch`, `missing_target`, `missing_legacy`, `duplicate`,
  `invalid_key`; bounded fuzzy candidates with score and reason, never auto-approved.
- In-memory review queue (Approve / Reject / Needs review) carried into reruns.
- Downloads: deterministic JSON audit package (no raw values), redacted Markdown report, SQL
  for re-checking.
- FastAPI API (`migration-workbench`, loopback-only unless `--allow-remote`) and a Next.js UI
  (`apps/web`) that calls it. Synthetic sample data ships in the API package.
- Tests: `evals/tests` (pytest, 10 files) and `apps/web/tests/report.test.mjs`; CI also builds
  the wheel and checks the console script and sample data.

## How to run

```bash
uv sync --all-extras          # from uv.lock; or: pip install -e ".[parquet]"
uv run migration-workbench    # API on http://127.0.0.1:8765
cd apps/web && npm ci && npm run dev
```

## Observability

Opt-in Sentry in the API process: `sentry` extra + `SENTRY_DSN` (initialised by the CLI before
uvicorn starts). Errors only; the allowlist scrubber keeps exception types, frame locations and
the request method/path, and redacts every message not on a static allowlist (empty today).
gap: the Next.js UI has no Sentry (local-only UI, no host).

## AI

None. No LLM or external service receives data; mismatch reasons are deterministic rules.

## Limits

- Local-only prototype: no authentication, no persistent storage, no production database
  connectors, no deployment (`deploy/README.md` lists what a pilot would need).
- Review state is in memory and lost on restart.
- No live URL.

## Disposition

Keep as a local lab tool / service demo.
