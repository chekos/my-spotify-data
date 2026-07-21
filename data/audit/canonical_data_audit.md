# Canonical Spotify Data Audit

Source ref: `origin/main`
Source fingerprint: `1c4bb9b8751e1d73a98e1d47d429e4931c776486b495a03acd3d67e37393636d`

## Union

- Events: `68672`
- Tracks: `8068`
- Earliest: `2018-01-10T19:46:56Z`
- Latest: `2026-07-21T21:52:29.823Z`
- Timestamp collisions: `610`

## Sources

### spotify-git-scraping_api_recently_played

- Repo/path: `spotify-git-scraping:data/recently_played.json`
- Source ref: `origin/main`
- Unique events: `14842`
- Unique tracks: `2948`
- Range: `2022-08-10T20:50:04.612Z` to `2026-06-24T14:48:02.110Z`
- Event-set hash: `070525637a1343d11936755ddf351b5ef5c66e239cae3b37763cdb92f58aea7f`

### my-spotify-data_api_recently_played

- Repo/path: `my-spotify-data:data/recently_played.json`
- Source ref: `origin/main`
- Unique events: `15873`
- Unique tracks: `3069`
- Range: `2022-08-10T20:50:04.612Z` to `2026-06-24T14:48:02.110Z`
- Event-set hash: `24d88238bff2e4c7f60ffbe4efbfc4f73ad932fce29e0e60b14d21ef7791ff56`

### my-esporifai_recent_history

- Repo/path: `my-esporifai:history.json`
- Source ref: `origin/main`
- Unique events: `14841`
- Unique tracks: `2948`
- Range: `2022-08-10T20:50:04.612Z` to `2026-06-24T14:48:02.110Z`
- Event-set hash: `7895fd9ddc6f6fde4813cdb74e90a43d4bf9530ab6eb47830ce36cdf82159903`

### my-esporifai_spotify_account_export

- Repo/path: `my-esporifai:streaming_history.json`
- Source ref: `origin/main`
- Unique events: `52629`
- Unique tracks: `6738`
- Range: `2018-01-10T19:46:56Z` to `2023-06-26T23:20:53Z`
- Event-set hash: `2373d382fca7abc8abf090983229090fc71452136d3d90dff05ab60dee58891a`

## Coverage

- `PASS` `my-esporifai_recent_history` subset of canonical events; missing `0`.
- `PASS` `my-esporifai_spotify_account_export` subset of canonical events; missing `0`.
- `PASS` `my-spotify-data_api_recently_played` subset of canonical events; missing `0`.
- `PASS` `spotify-git-scraping_api_recently_played` subset of canonical events; missing `0`.

## Catalog

- Track records: `8068`
- Track records missing metadata: `0`
- Album records: `4339`
- Artist records: `3298`
- Spotify catalog enrichment: `True`
- Spotify enrichment requested tracks: `0`
- Spotify enrichment returned tracks: `0`
