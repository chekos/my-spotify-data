# my-spotify-data

Public canonical source data for my Spotify listening history.

This repo preserves the merged listening-event history from the older
Spotify/git-scraping repos while keeping the committed source files stable and
deterministic. Generated analytics, SQLite databases, rendered pages, and
screenshots belong in `my-spotify-analytics`, not here.

Current migration status is tracked in `docs/migration-status.md`.

## Canonical Files

- `data/listening_events.jsonl`: one normalized listening event per line,
  sorted by `played_at` and `track_id`.
- `data/track_catalog.jsonl`: one track catalog record per Spotify track ID.
  Export-only tracks that still need metadata are retained with
  `"metadata_status":"missing"` rather than dropped.
- `data/album_catalog.jsonl`: normalized album metadata collected from the
  available API/catalog sources.
- `data/artist_catalog.jsonl`: normalized artist metadata collected from the
  available API/catalog sources.
- `data/audit/canonical_data_audit.md`: human-readable proof of source coverage.
- `data/audit/canonical_data_audit.json`: machine-readable audit details,
  checksums, source refs, and coverage checks.

The current canonical audit records the event count, date range, catalog counts,
source checksums, and coverage checks. Use the audit files for live counts rather
than copying those values into prose.

Canonical history is rebuilt from:

- `spotify-git-scraping`
- `my-spotify-data`
- `my-esporifai/history.json`
- `my-esporifai/streaming_history.json`

## Rebuild

From the grouped workspace root layout:

```shell
cd my-spotify-data
uv run --python 3.12 --with-requirements requirements.txt \
  python scripts/build_canonical_data.py --enrich-missing-tracks
uv run --python 3.12 --with-requirements requirements.txt \
  python -m unittest discover -s tests -p 'test_*.py'
```

The builder reads sibling repos through Git refs, defaults to `origin/main`, and
is expected to be idempotent. A second run should report `"changed_files": []`
when source refs have not changed.

## Automation

`.github/workflows/canonical-data.yml` rebuilds the stable canonical files from
full Git history and commits only those explicit files when they change. The
workflow checks out `spotify-git-scraping` and `my-esporifai` as sibling repos so
the no-data-loss audit remains reproducible while the old repos are still
available.

This is the only scheduled raw Spotify fetcher in the repo family. Older
git-scraping/data repos are retained as historical source material and recovery
references.

The older `recently-played.yml` and `top-items.yml` workflows in this repo are
kept for recovery reference but disabled in GitHub Actions; the canonical data
workflow owns regular data refreshes.

## Spotify authentication recovery

Spotify refresh tokens expire six months after authorization; refreshing access
tokens does not extend that lifetime. See the
[Spotify expiration policy](https://developer.spotify.com/blog/2026-06-18-refresh-token-expiration).
An `invalid_grant` response requires a new user authorization, while
`invalid_client` requires checking the app credentials.

Run the manual `Check Spotify authentication` workflow to diagnose failures.
Its error output excludes raw OAuth responses and credentials. On failure, its
one-day `spotify-public-config` artifact contains only the public client ID and
registered redirect URI needed to prepare sign-in. Never upload access tokens,
refresh tokens, client secrets, or authorization codes as workflow artifacts.
