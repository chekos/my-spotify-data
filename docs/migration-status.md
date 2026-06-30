# Spotify repo migration status

Status date: 2026-06-30

## Current ownership

- `my-spotify-data` is the canonical public data source. It owns normalized
  listening events, catalog JSONL files, and audit artifacts.
- `my-spotify-analytics` renders SQLite-backed GitHub Pages analytics from
  `my-spotify-data`. Generated databases, pages, and screenshots are not
  committed to `my-spotify-data`.
- `esporifai` is the reusable Spotify API CLI/package used by automation.
- `spotify-git-scraping` and `my-esporifai` remain historical source inputs
  because the canonical audit still rebuilds from their full Git histories.
- `git-scraping-spotify` and `my-recently-played-tracks` are historical derived
  dataset/page repos.

## Automation posture

- Keep `my-spotify-data/.github/workflows/canonical-data.yml` scheduled. It is
  the hourly canonical data builder and the only scheduled raw Spotify fetcher.
- Keep `my-spotify-data/.github/workflows/adhoc.yml` active as a manual auth and
  API smoke test.
- Keep `my-spotify-data/.github/workflows/recently-played.yml` and
  `my-spotify-data/.github/workflows/top-items.yml` disabled. They are retained
  as recovery references, but the canonical builder now owns data refreshes.
- Keep `my-spotify-analytics/.github/workflows/pages.yml` scheduled. It rebuilds
  the public GitHub Pages site from the latest canonical data.
- Keep `esporifai` CI and publish workflows active for package maintenance.
- Legacy data and derived-output workflows are retained in their repositories
  for recovery reference, but they should stay disabled in GitHub Actions unless
  there is a deliberate recovery run.

## Health snapshot

The current source of truth for counts is `data/audit/canonical_data_audit.json`
and its Markdown companion. At the time this status note was written, the audit
reported complete coverage for all legacy sources and zero track records missing
metadata.

The public analytics site is built from this repo by `my-spotify-analytics`:

- https://chekos.github.io/my-spotify-analytics/

## Maintenance commands

From the grouped workspace root:

```shell
cd my-spotify-data
uv run --python 3.12 --with-requirements requirements.txt \
  python -m unittest discover -s tests -p 'test_*.py'

cd ../my-spotify-analytics
uv run --python 3.12 python -m unittest discover -s tests -p 'test_*.py'

cd ../esporifai
uv run --python 3.12 --extra test python -m pytest -m "not integration"
```

Before changing any repo in this workspace, check that repo's independent branch
and worktree status.
