# my-spotify-data

Public canonical source data for my Spotify listening history.

This repo preserves the merged listening-event history from the older
Spotify/git-scraping repos while keeping the committed source files stable and
deterministic. Generated analytics, SQLite databases, rendered pages, and
screenshots belong in `my-spotify-analytics`, not here.

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

The current canonical audit preserves 68,499 unique `(played_at, track_id)`
events across:

- `spotify-git-scraping`
- `my-spotify-data`
- `my-esporifai/history.json`
- `my-esporifai/streaming_history.json`

## Rebuild

From the grouped workspace root layout:

```shell
python3 scripts/build_canonical_data.py
python3 -m unittest discover -s tests -p 'test_*.py'
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
