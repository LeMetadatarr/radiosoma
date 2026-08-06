# radiosoma — agent guide

Python client for the SomaFM public channels API, with mediavocab converters. Parses `channels.xml` into `SomaFmStation` objects and recent-tracks feeds into dicts, then maps both to typed `mediavocab` records.

## Setup

```bash
pip install -e .[test]      # runtime + pytest/vcrpy/pytest-vcr
pip install -e .[stealth]   # optional curl_cffi transport
```

Runtime deps: `requests`, `mediavocab>=1.0.0`. Python `>=3.8`.

## Test

```bash
pytest test/
```

Tests are cassette-backed (VCR). `test/conftest.py` pins `record_mode: none`, so the suite replays captured responses under `test/cassettes/` and never hits the network. Re-record locally when upstream drifts:

```bash
pytest --vcr-record=all test/test_somafm_vcr.py
```

## Lint/Typecheck

Ruff via the shared `lint.yml` workflow (`ruff: true`, pre-commit off). No local config file checked in; run `ruff check .`. No type-checker configured (code uses inline type hints but no mypy gate).

## Layout

- `radiosoma/__init__.py` — public API: `get_stations()`, `get_recent_tracks()`, `SomaFmStation`, `StreamVariant`. XML parsing (`_xml2dict`/`_etree2dict`), bitrate extraction from PLS filenames, codec/container mapping. No mediavocab import here.
- `radiosoma/converters.py` — mediavocab mappers: `station_to_release` (best stream), `station_to_releases` (one `Release` per variant), `song_to_programme`, `recent_tracks_to_programmes`, `recent_tracks_to_schedule`. Holds the `_GENRE_MAP` SOMA-tag → `mediavocab.taxonomy.genre` table.
- `radiosoma/transport.py` — `default_session()`; returns `requests.Session`, or a Chrome-impersonating `curl_cffi` session when `RADIOSOMA_TRANSPORT=curl_cffi`.
- `radiosoma/version.py` — version string (do not edit).
- `test/` — VCR tests (`test_somafm_vcr.py`), import/converter/transport/coverage tests, cassettes.
- `docs/`, `examples/` — getting-started, API, converter and transport docs; six runnable examples.

## Conventions (Org hard rules)

- Branches: `dev` (work) / `master` (stable). NEVER `main`.
- Never edit `radiosoma/version.py` — gh-automations bumps semver from conventional-commit prefixes (`feat:` / `fix:` / `feat!:`).
- New repos private by default; do not make source public without asking.
- Commit identity: JarbasAi <jarbasai@mailfence.com>.
- Reference `OpenVoiceOS/gh-automations` reusable workflows at `@dev`.
- No Neon / `neon-*` references.
- No meta-commentary (no history, dates, "before times"); describe current state only.
- CI is provided by OpenVoiceOS/gh-automations.

## Gotchas

- The data model is split: `SomaFmStation` and stream parsing carry no mediavocab dependency; all typing lives in `converters.py`. Keep parsing and mediavocab mapping separate.
- Bitrate is parsed from the PLS filename suffix (e.g. `groovesalad130.pls` → `130`); a suffix-less filename falls back to the legacy `128` MP3 default.
- SOMA `format` attributes map to canonical codecs: `aac` → `aac`, `aacp` → `he-aac`, `mp3` → `mp3`. `aacp` is HE-AAC, not plain AAC.
- `station_to_release` returns a valid empty `Release` (blank `uri`) when a channel has no stream variants — callers always get an object.
- `recent_tracks_to_schedule` chains each programme's `ends_at` to the next programme's `starts_at`; `Schedule` requires non-tail programmes to have `ends_at`.
- Genres are tokenised on both `,` and `|`; unmapped tokens pass through as raw lower-cased strings (taxonomy escape hatch).
- `default_session()` only impersonates a browser when both the env var is set and `curl_cffi` is installed; otherwise it silently uses `requests`. SomaFM is an open API and does not need stealth — the transport exists for family-wide uniformity.
- `nightly-live.yml` re-records cassettes against live endpoints in detect-only mode (not committed). A red nightly means cassettes need local re-recording, not a code change.
