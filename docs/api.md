# radiosoma API

`radiosoma` is a thin Python client for the [SomaFM](https://somafm.com) public channels API.

## get_stations()

```python
from radiosoma import get_stations

for station in get_stations():
    print(station.title, station.best_stream)
```

Returns a generator of `SomaFmStation` objects.

## SomaFmStation

### Properties

| Property | Type | Description |
|---|---|---|
| `station_id` | `str` | Short identifier (e.g. `"groovesalad"`) |
| `title` | `str` | Human-readable name |
| `description` | `str` | Station description |
| `genre` | `str` | Music genre tag (raw, may use `,` or `\|` separators) |
| `image` | `str \| None` | URL of the largest available image |
| `dj` | `str` | DJ name (empty if none) |
| `listeners` | `int \| None` | Current listener count |
| `last_playing` | `str` | Last-played track string from `<lastPlaying>` |
| `updated` | `int \| None` | Server-side update epoch |
| `streams` | `list[str]` | All available playlist URLs |
| `stream_variants` | `list[StreamVariant]` | Typed variants with `format`, `bitrate`, `codec`, `container`, `source` |
| `best_stream` | `str \| None` | Highest-quality playlist URL |
| `fastest_stream` | `str \| None` | Lowest-latency playlist URL |
| `m3u_stream` | `str` | Constructed `.m3u` URL |
| `direct_stream` | `str` | Direct MP3 stream URL (ice2) |
| `alt_direct_stream` | `str` | Alternate direct MP3 stream (ice4) |

### StreamVariant

| Attribute | Description |
|---|---|
| `url` | Playlist URL |
| `format` | SOMA format tag (`aac`, `aacp`, `mp3`) |
| `bitrate` | kbps figure parsed from the playlist filename (e.g. `"130"`) |
| `codec` | Canonical codec hint (`aac`, `he-aac`, `mp3`) |
| `container` | Canonical container hint (`adts`, `mp3`) |
| `source` | `"highestpls"`, `"fastpls"`, or `"slowpls"` |

### Stream URL priority

- `best_stream` — first `highestpls`, falls back to `fastpls`/`slowpls`.
- `fastest_stream` — first `fastpls`, falls back to `highestpls`/`slowpls`.
- `direct_stream` / `alt_direct_stream` — always available, constructed from `station_id`.

## get_recent_tracks(channel_id)

```python
from radiosoma import get_recent_tracks

for song in get_recent_tracks("groovesalad"):
    print(song["artist"], "-", song["title"])
```

Returns a list of dicts (most recent first) with keys `title`, `artist`,
`album`, `albumart`, `date` (unix epoch as string).

## mediavocab converters

`radiosoma.converters` translates radiosoma data into the canonical
[mediavocab](https://github.com/JarbasAl/mediavocab) types.

### Modality

```python
from radiosoma.converters import MODALITY  # {PlaybackType.AUDIO}
```

### `station_to_release(station) -> Release`

Returns a single `mediavocab.Release` for the highest-quality stream:

- `work.media_type == MediaType.RADIO`
- `work.country == "US"`, `work.language == "en"`
- `work.runtime is None` (continuous live broadcast)
- `work.content_genres` resolved against `mediavocab.taxonomy.genre.GENRE_*`
  (unmapped tokens fall through as raw lower-cased strings)
- `work.external_ids["soma_fm_channel_id"]` is the SOMA channel id (string)
- `stream_mode == StreamMode.CONTINUOUS`
- `codec`, `container`, `bitrate`, `audio_channels="stereo"`, `audio_language="en"`
- `uri` is the best available stream URL
- `image` is the largest channel artwork

### `station_to_releases(station) -> list[Release]`

One `Release` per stream variant SOMA exposes (typically four:
high-quality AAC, MP3, low-bitrate HE-AAC, lo-fi HE-AAC). All releases
share the same underlying `Work` so consumers can deduplicate by
identity.

### `song_to_work(song, station) -> Work | None`

Builds a `MediaType.MUSIC` `Work` from a single recent-tracks dict
(returns `None` for an entry with no title). The Work's:

- `title` is the song title.
- `credits` carries the artist as a `PERFORMER` `Credit` (when present).
- `extra` holds the ephemeral play state: `played_at` (ISO datetime
  derived from the unix `date` field, falling back to now), `album`,
  `albumart`, and the channel's `soma_fm_channel_id`.

A now-playing time is delivery-time state, not catalogue identity, so it
rides in `extra` — there is no schedule/programme vocabulary type
(mediavocab axiom A3).

### `recent_tracks_to_works(songs, station) -> list[Work]`

Maps the recent-tracks feed to a list of `MUSIC` Works, most-recent
first; entries with empty titles are filtered out.
