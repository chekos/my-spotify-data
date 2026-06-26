from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_canonical_data.py"
SPEC = importlib.util.spec_from_file_location("build_canonical_data", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def sample_recently_played_item(track_id: str = "track-1", played_at: str = "2026-01-01T00:00:00Z"):
    return {
        "played_at": played_at,
        "track": {
            "id": track_id,
            "name": "Song",
            "duration_ms": 120000,
            "explicit": False,
            "popularity": 42,
            "uri": f"spotify:track:{track_id}",
            "href": f"https://api.spotify.com/v1/tracks/{track_id}",
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
            "external_ids": {"isrc": "ISRC"},
            "artists": [
                {
                    "id": "artist-1",
                    "name": "Artist",
                    "uri": "spotify:artist:artist-1",
                    "href": "https://api.spotify.com/v1/artists/artist-1",
                    "external_urls": {"spotify": "https://open.spotify.com/artist/artist-1"},
                    "type": "artist",
                }
            ],
            "album": {
                "id": "album-1",
                "name": "Album",
                "album_type": "album",
                "artists": [
                    {
                        "id": "artist-1",
                        "name": "Artist",
                        "uri": "spotify:artist:artist-1",
                        "href": "https://api.spotify.com/v1/artists/artist-1",
                        "external_urls": {"spotify": "https://open.spotify.com/artist/artist-1"},
                        "type": "artist",
                    }
                ],
                "release_date": "2026-01-01",
                "release_date_precision": "day",
                "total_tracks": 10,
                "uri": "spotify:album:album-1",
                "href": "https://api.spotify.com/v1/albums/album-1",
                "external_urls": {"spotify": "https://open.spotify.com/album/album-1"},
                "images": [],
                "type": "album",
            },
        },
    }


class BuildCanonicalDataTest(unittest.TestCase):
    def test_json_items_accepts_array_and_response_object(self):
        array_payload = json.dumps([sample_recently_played_item()]).encode()
        object_payload = json.dumps({"items": [sample_recently_played_item()]}).encode()

        array_items, array_shape = builder.json_items(array_payload)
        object_items, object_shape = builder.json_items(object_payload)

        self.assertEqual("array", array_shape)
        self.assertEqual("object", object_shape)
        self.assertEqual("track-1", array_items[0]["track"]["id"])
        self.assertEqual("track-1", object_items[0]["track"]["id"])

    def test_ingest_recently_played_item_creates_event_and_catalog_records(self):
        events = {}
        tracks = {}
        albums = {}
        artists = {}

        builder.ingest_recently_played_item(
            sample_recently_played_item(),
            "test_source",
            events,
            tracks,
            albums,
            artists,
        )

        self.assertEqual([("2026-01-01T00:00:00Z", "track-1")], list(events))
        self.assertEqual(["test_source"], events[("2026-01-01T00:00:00Z", "track-1")]["sources"])
        self.assertEqual("Song", tracks["track-1"]["name"])
        self.assertEqual("album-1", tracks["track-1"]["album_id"])
        self.assertEqual("Album", albums["album-1"]["name"])
        self.assertEqual("Artist", artists["artist-1"]["name"])

    def test_add_event_merges_sources_without_duplicates(self):
        events = {}

        builder.add_event(events, "2026-01-01T00:00:00Z", "track-1", "source_b")
        builder.add_event(events, "2026-01-01T00:00:00Z", "track-1", "source_a")
        builder.add_event(events, "2026-01-01T00:00:00Z", "track-1", "source_a")

        self.assertEqual(
            ["source_a", "source_b"],
            events[("2026-01-01T00:00:00Z", "track-1")]["sources"],
        )

    def test_missing_track_stubs_preserve_export_only_events(self):
        events = {
            ("2020-01-01T00:00:00Z", "missing-track"): {
                "played_at": "2020-01-01T00:00:00Z",
                "track_id": "missing-track",
                "sources": ["export"],
            }
        }
        tracks = {}

        builder.add_missing_track_stubs(events, tracks)

        self.assertEqual("missing", tracks["missing-track"]["metadata_status"])

    def test_collision_report_finds_same_timestamp_different_track(self):
        events = {
            ("2026-01-01T00:00:00Z", "track-1"): {},
            ("2026-01-01T00:00:00Z", "track-2"): {},
            ("2026-01-02T00:00:00Z", "track-1"): {},
        }

        self.assertEqual(
            {"2026-01-01T00:00:00Z": ["track-1", "track-2"]},
            builder.collision_report(events),
        )

    def test_source_fingerprint_ignores_unrelated_repo_head_changes(self):
        first_summary = builder.SourceSummary(
            "source",
            "repo",
            "data/recently_played.json",
            "origin/main",
            "data-commit-1",
        )
        second_summary = builder.SourceSummary(
            "source",
            "repo",
            "data/recently_played.json",
            "origin/main",
            "workflow-only-head-change",
        )
        first_summary.source_hash = "same-event-set"
        second_summary.source_hash = "same-event-set"
        events = [
            {
                "played_at": "2026-01-01T00:00:00Z",
                "track_id": "track-1",
                "sources": ["source"],
            }
        ]
        tracks = [{"id": "track-1", "metadata_status": "complete"}]

        self.assertEqual(
            builder.source_fingerprint([first_summary], events, tracks, [], []),
            builder.source_fingerprint([second_summary], events, tracks, [], []),
        )


if __name__ == "__main__":
    unittest.main()
