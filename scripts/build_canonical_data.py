#!/usr/bin/env python3
"""Build canonical Spotify listening data from the legacy repo family.

The script is intentionally stdlib-only so it can run in a bare checkout. It
reads source repositories through Git plumbing instead of checking out old
commits, then writes deterministic JSONL files and an audit report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


Json = dict[str, Any]


@dataclass
class SourceSummary:
    name: str
    repo: str
    path: str
    ref: str
    resolved_ref: str
    commits: int = 0
    snapshots_with_items: int = 0
    shape_counts: Counter[str] = field(default_factory=Counter)
    bad_payloads: int = 0
    unique_events: int = 0
    unique_tracks: int = 0
    earliest: str | None = None
    latest: str | None = None
    source_hash: str | None = None

    def as_dict(self) -> Json:
        return {
            "name": self.name,
            "repo": self.repo,
            "path": self.path,
            "ref": self.ref,
            "resolved_ref": self.resolved_ref,
            "commits": self.commits,
            "snapshots_with_items": self.snapshots_with_items,
            "shape_counts": dict(self.shape_counts),
            "bad_payloads": self.bad_payloads,
            "unique_events": self.unique_events,
            "unique_tracks": self.unique_tracks,
            "earliest": self.earliest,
            "latest": self.latest,
            "source_hash": self.source_hash,
        }


def run_git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stderr=subprocess.PIPE,
    )


def resolve_ref(repo: Path, ref: str) -> str:
    return run_git(repo, "rev-parse", ref).decode().strip()


def file_commits(repo: Path, ref: str, path: str) -> list[str]:
    output = run_git(repo, "log", "--reverse", "--format=%H", ref, "--", path)
    return [line for line in output.decode().splitlines() if line]


def cat_file_versions(repo: Path, commits: list[str], path: str) -> list[bytes]:
    if not commits:
        return []

    specs = "".join(f"{commit}:{path}\n" for commit in commits).encode()
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(specs)
    if process.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace"))

    payloads: list[bytes] = []
    pos = 0
    for _commit in commits:
        nl = stdout.find(b"\n", pos)
        if nl == -1:
            raise RuntimeError("Malformed git cat-file output")
        header = stdout[pos:nl].decode(errors="replace")
        pos = nl + 1
        parts = header.split()
        if len(parts) < 3 or parts[1] != "blob":
            raise RuntimeError(f"Unexpected git cat-file header: {header}")
        size = int(parts[2])
        payloads.append(stdout[pos : pos + size])
        pos += size + 1
    return payloads


def compact_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def load_json(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))


def json_items(payload: bytes) -> tuple[list[Json], str]:
    data = load_json(payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], "array"
    if isinstance(data, dict):
        items = data.get("items") or []
        return [item for item in items if isinstance(item, dict)], "object"
    return [], type(data).__name__


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def artist_id_list(raw_artists: Any) -> list[str]:
    if not isinstance(raw_artists, list):
        return []

    ids: list[str] = []
    for artist in raw_artists:
        if isinstance(artist, dict) and artist.get("id"):
            ids.append(artist["id"])
        elif isinstance(artist, str):
            ids.append(artist)
    return ids


def normalize_artist(artist: Json, source: str) -> Json | None:
    artist_id = artist.get("id")
    if not artist_id:
        return None
    return {
        "id": artist_id,
        "name": artist.get("name"),
        "uri": artist.get("uri"),
        "href": artist.get("href"),
        "external_urls": artist.get("external_urls"),
        "type": artist.get("type"),
        "sources": [source],
    }


def normalize_album(album: Json, source: str) -> Json | None:
    album_id = album.get("id")
    if not album_id:
        return None
    return {
        "id": album_id,
        "name": album.get("name"),
        "album_type": album.get("album_type"),
        "artist_ids": artist_id_list(album.get("artists")),
        "release_date": album.get("release_date"),
        "release_date_precision": album.get("release_date_precision"),
        "total_tracks": album.get("total_tracks"),
        "uri": album.get("uri"),
        "href": album.get("href"),
        "external_urls": album.get("external_urls"),
        "images": album.get("images"),
        "type": album.get("type"),
        "sources": [source],
    }


def normalize_track(track: Json, source: str) -> Json | None:
    track_id = track.get("id")
    if not track_id:
        return None

    album = track.get("album") if isinstance(track.get("album"), dict) else {}
    artist_ids = artist_id_list(track.get("artists"))
    album_id = first_present(track.get("album_id"), album.get("id"))

    return {
        "id": track_id,
        "name": track.get("name"),
        "artist_ids": first_present(track.get("artist_ids"), artist_ids, []),
        "album_id": album_id,
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
        "popularity": track.get("popularity"),
        "preview_url": track.get("preview_url"),
        "track_number": track.get("track_number"),
        "disc_number": track.get("disc_number"),
        "is_local": track.get("is_local"),
        "uri": track.get("uri"),
        "href": track.get("href"),
        "external_ids": track.get("external_ids"),
        "external_urls": track.get("external_urls"),
        "type": track.get("type"),
        "metadata_status": "complete",
        "sources": [source],
    }


def merge_record(records: dict[str, Json], record: Json | None) -> None:
    if not record:
        return
    record_id = record["id"]
    existing = records.get(record_id)
    if existing is None:
        clean = {key: value for key, value in record.items() if value not in (None, [], {})}
        clean["sources"] = sorted(set(record.get("sources", [])))
        records[record_id] = clean
        return

    for key, value in record.items():
        if key == "sources":
            existing["sources"] = sorted(set(existing.get("sources", [])) | set(value))
        elif value not in (None, [], {}) and existing.get(key) in (None, [], {}, ""):
            existing[key] = value


def add_event(events: dict[tuple[str, str], Json], played_at: str, track_id: str, source: str) -> None:
    key = (played_at, track_id)
    event = events.setdefault(
        key,
        {
            "played_at": played_at,
            "track_id": track_id,
            "sources": [],
        },
    )
    event["sources"] = sorted(set(event["sources"]) | {source})


def ingest_recently_played_item(
    item: Json,
    source: str,
    events: dict[tuple[str, str], Json],
    tracks: dict[str, Json],
    albums: dict[str, Json],
    artists: dict[str, Json],
) -> None:
    played_at = item.get("played_at")
    track = item.get("track") if isinstance(item.get("track"), dict) else {}
    track_id = track.get("id")
    if not played_at or not track_id:
        return

    add_event(events, played_at, track_id, source)
    merge_record(tracks, normalize_track(track, source))

    album = track.get("album") if isinstance(track.get("album"), dict) else None
    merge_record(albums, normalize_album(album, source) if album else None)
    if album:
        for artist in album.get("artists", []):
            if isinstance(artist, dict):
                merge_record(artists, normalize_artist(artist, source))
    for artist in track.get("artists", []):
        if isinstance(artist, dict):
            merge_record(artists, normalize_artist(artist, source))


def summarize_events(summary: SourceSummary, events: dict[tuple[str, str], Json]) -> None:
    keys = sorted(events)
    summary.unique_events = len(keys)
    summary.unique_tracks = len({track_id for _played_at, track_id in keys})
    if keys:
        summary.earliest = keys[0][0]
        summary.latest = keys[-1][0]


def ingest_recently_played_history(
    repo: Path,
    repo_name: str,
    ref: str,
    path: str,
    source: str,
    events: dict[tuple[str, str], Json],
    tracks: dict[str, Json],
    albums: dict[str, Json],
    artists: dict[str, Json],
) -> tuple[SourceSummary, set[tuple[str, str]]]:
    resolved_ref = resolve_ref(repo, ref)
    commits = file_commits(repo, ref, path)
    payloads = cat_file_versions(repo, commits, path)
    summary = SourceSummary(source, repo_name, path, ref, resolved_ref, commits=len(commits))
    source_events: dict[tuple[str, str], Json] = {}

    for payload in payloads:
        try:
            items, shape = json_items(payload)
        except Exception:
            summary.bad_payloads += 1
            continue
        summary.shape_counts[shape] += 1
        if items:
            summary.snapshots_with_items += 1
        for item in items:
            before_count = len(source_events)
            ingest_recently_played_item(item, source, source_events, tracks, albums, artists)
            if len(source_events) > before_count:
                played_at = item["played_at"]
                track_id = item["track"]["id"]
                add_event(events, played_at, track_id, source)

    summarize_events(summary, source_events)
    summary.source_hash = compact_hash(sorted(f"{played_at}|{track_id}" for played_at, track_id in source_events))
    return summary, set(source_events)


def git_show_json(repo: Path, ref: str, path: str) -> Any:
    return load_json(run_git(repo, "show", f"{ref}:{path}"))


def ingest_export_events(
    repo: Path,
    repo_name: str,
    ref: str,
    path: str,
    source: str,
    events: dict[tuple[str, str], Json],
) -> tuple[SourceSummary, set[tuple[str, str]]]:
    resolved_ref = resolve_ref(repo, ref)
    data = git_show_json(repo, ref, path)
    summary = SourceSummary(source, repo_name, path, ref, resolved_ref, commits=1)
    source_events: dict[tuple[str, str], Json] = {}

    if not isinstance(data, list):
        summary.bad_payloads = 1
        return summary, set()

    summary.shape_counts["array"] = 1
    summary.snapshots_with_items = 1 if data else 0
    for item in data:
        if not isinstance(item, dict):
            continue
        played_at = first_present(item.get("played_at"), item.get("ts"))
        track_id = first_present(
            item.get("id"),
            (item.get("spotify_track_uri") or "").removeprefix("spotify:track:"),
        )
        if played_at and track_id:
            add_event(source_events, played_at, track_id, source)
            add_event(events, played_at, track_id, source)

    summarize_events(summary, source_events)
    summary.source_hash = compact_hash(sorted(f"{played_at}|{track_id}" for played_at, track_id in source_events))
    return summary, set(source_events)


def ingest_catalog_file(
    repo: Path,
    ref: str,
    path: str,
    source: str,
    kind: str,
    records: dict[str, Json],
) -> None:
    data = git_show_json(repo, ref, path)
    if not isinstance(data, list):
        return
    normalizers = {
        "track": normalize_track,
        "album": normalize_album,
        "artist": normalize_artist,
    }
    normalizer = normalizers[kind]
    for item in data:
        if isinstance(item, dict):
            merge_record(records, normalizer(item, source))


def add_missing_track_stubs(events: dict[tuple[str, str], Json], tracks: dict[str, Json]) -> None:
    for _played_at, track_id in events:
        if track_id not in tracks:
            tracks[track_id] = {
                "id": track_id,
                "metadata_status": "missing",
                "sources": ["event_without_catalog_metadata"],
            }


def sorted_jsonl(records: list[Json]) -> str:
    lines = [
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for record in records
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def write_text_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text() == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def write_jsonl(path: Path, records: list[Json]) -> bool:
    return write_text_if_changed(path, sorted_jsonl(records))


def collision_report(events: dict[tuple[str, str], Json]) -> dict[str, list[str]]:
    by_played_at: dict[str, set[str]] = {}
    for played_at, track_id in events:
        by_played_at.setdefault(played_at, set()).add(track_id)
    return {
        played_at: sorted(track_ids)
        for played_at, track_ids in sorted(by_played_at.items())
        if len(track_ids) > 1
    }


def markdown_audit(audit: Json) -> str:
    lines = [
        "# Canonical Spotify Data Audit",
        "",
        f"Source ref: `{audit['source_ref']}`",
        f"Source fingerprint: `{audit['source_fingerprint']}`",
        "",
        "## Union",
        "",
        f"- Events: `{audit['union']['events']}`",
        f"- Tracks: `{audit['union']['tracks']}`",
        f"- Earliest: `{audit['union']['earliest']}`",
        f"- Latest: `{audit['union']['latest']}`",
        f"- Timestamp collisions: `{audit['union']['timestamp_collision_count']}`",
        "",
        "## Sources",
        "",
    ]
    for source in audit["sources"]:
        lines.extend(
            [
                f"### {source['name']}",
                "",
                f"- Repo/path: `{source['repo']}:{source['path']}`",
                f"- Ref: `{source['ref']}` -> `{source['resolved_ref']}`",
                f"- File versions: `{source['commits']}`",
                f"- Snapshots with items: `{source['snapshots_with_items']}`",
                f"- Unique events: `{source['unique_events']}`",
                f"- Unique tracks: `{source['unique_tracks']}`",
                f"- Range: `{source['earliest']}` to `{source['latest']}`",
                f"- Event-set hash: `{source['source_hash']}`",
                "",
            ]
        )
    lines.extend(["## Coverage", ""])
    for check in audit["coverage_checks"]:
        status = "PASS" if check["missing_count"] == 0 else "FAIL"
        lines.append(
            f"- `{status}` `{check['source']}` subset of canonical events; missing `{check['missing_count']}`."
        )
    lines.extend(
        [
            "",
            "## Catalog",
            "",
            f"- Track records: `{audit['catalog']['tracks']}`",
            f"- Track records missing metadata: `{audit['catalog']['tracks_missing_metadata']}`",
            f"- Album records: `{audit['catalog']['albums']}`",
            f"- Artist records: `{audit['catalog']['artists']}`",
            "",
        ]
    )
    return "\n".join(lines)


def build(args: argparse.Namespace) -> Json:
    repo_root = Path(args.repo_root).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    data_dir = repo_root / args.data_dir

    events: dict[tuple[str, str], Json] = {}
    tracks: dict[str, Json] = {}
    albums: dict[str, Json] = {}
    artists: dict[str, Json] = {}
    source_sets: dict[str, set[tuple[str, str]]] = {}
    summaries: list[SourceSummary] = []

    source_configs = [
        (
            "spotify-git-scraping_api_recently_played",
            "spotify-git-scraping",
            "data/recently_played.json",
        ),
        (
            "my-spotify-data_api_recently_played",
            "my-spotify-data",
            "data/recently_played.json",
        ),
    ]

    for source, repo_name, path in source_configs:
        summary, source_events = ingest_recently_played_history(
            workspace_root / repo_name,
            repo_name,
            args.source_ref,
            path,
            source,
            events,
            tracks,
            albums,
            artists,
        )
        summaries.append(summary)
        source_sets[source] = source_events

    esporifai_repo = workspace_root / "my-esporifai"
    for source, path in [
        ("my-esporifai_recent_history", "history.json"),
        ("my-esporifai_spotify_account_export", "streaming_history.json"),
    ]:
        summary, source_events = ingest_export_events(
            esporifai_repo,
            "my-esporifai",
            args.source_ref,
            path,
            source,
            events,
        )
        summaries.append(summary)
        source_sets[source] = source_events

    ingest_catalog_file(esporifai_repo, args.source_ref, "tracks.json", "my-esporifai_catalog", "track", tracks)
    ingest_catalog_file(esporifai_repo, args.source_ref, "albums.json", "my-esporifai_catalog", "album", albums)
    ingest_catalog_file(esporifai_repo, args.source_ref, "artists.json", "my-esporifai_catalog", "artist", artists)
    add_missing_track_stubs(events, tracks)

    event_records = [events[key] for key in sorted(events)]
    track_records = [tracks[key] for key in sorted(tracks)]
    album_records = [albums[key] for key in sorted(albums)]
    artist_records = [artists[key] for key in sorted(artists)]

    collisions = collision_report(events)
    union_keys = set(events)
    coverage_checks = []
    for source, keys in sorted(source_sets.items()):
        missing = sorted(keys - union_keys)
        coverage_checks.append(
            {
                "source": source,
                "source_events": len(keys),
                "missing_count": len(missing),
                "missing_examples": [f"{played_at}|{track_id}" for played_at, track_id in missing[:20]],
            }
        )

    audit = {
        "source_ref": args.source_ref,
        "source_fingerprint": compact_hash(
            [f"{summary.name}:{summary.resolved_ref}" for summary in summaries]
        ),
        "union": {
            "events": len(event_records),
            "tracks": len({record["track_id"] for record in event_records}),
            "earliest": event_records[0]["played_at"] if event_records else None,
            "latest": event_records[-1]["played_at"] if event_records else None,
            "timestamp_collision_count": len(collisions),
            "timestamp_collision_examples": dict(list(collisions.items())[:20]),
            "event_set_hash": compact_hash([f"{played_at}|{track_id}" for played_at, track_id in sorted(events)]),
        },
        "sources": [summary.as_dict() for summary in summaries],
        "coverage_checks": coverage_checks,
        "catalog": {
            "tracks": len(track_records),
            "tracks_missing_metadata": sum(1 for record in track_records if record.get("metadata_status") == "missing"),
            "albums": len(album_records),
            "artists": len(artist_records),
        },
    }

    changed = []
    outputs = {
        data_dir / "listening_events.jsonl": event_records,
        data_dir / "track_catalog.jsonl": track_records,
        data_dir / "album_catalog.jsonl": album_records,
        data_dir / "artist_catalog.jsonl": artist_records,
    }
    for path, records in outputs.items():
        if write_jsonl(path, records):
            changed.append(str(path.relative_to(repo_root)))

    audit_json = json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if write_text_if_changed(data_dir / "audit" / "canonical_data_audit.json", audit_json):
        changed.append(str((data_dir / "audit" / "canonical_data_audit.json").relative_to(repo_root)))
    if write_text_if_changed(data_dir / "audit" / "canonical_data_audit.md", markdown_audit(audit)):
        changed.append(str((data_dir / "audit" / "canonical_data_audit.md").relative_to(repo_root)))

    audit["changed_files"] = changed
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workspace-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-ref", default="origin/main")
    parser.add_argument("--data-dir", default="data")
    return parser.parse_args()


def main() -> None:
    audit = build(parse_args())
    print(json.dumps({"union": audit["union"], "catalog": audit["catalog"], "changed_files": audit["changed_files"]}, indent=2))


if __name__ == "__main__":
    main()
