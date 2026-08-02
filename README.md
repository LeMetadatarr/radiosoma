# radiosoma

Python client for the [SomaFM](https://somafm.com) public channels API,
modelled with [mediavocab](https://github.com/TigreGotico/mediavocab) as the
canonical media vocabulary.

## Install

```bash
pip install radiosoma
```

## Modelling

SOMA FM channels follow mediavocab axiom 8:

* Each channel is a `Work` with `MediaType.RADIO` (live-linear broadcast).
* Each distinct stream encoding (130 kbps AAC, 256 kbps MP3, 64 kbps
  HE-AAC, 32 kbps HE-AAC) is a separate `Release` of the same `Work`,
  with `StreamMode.CONTINUOUS`.
* The provider is audio-only (`PlaybackType.AUDIO`).
* Each recently-played song from the recent-tracks feed surfaces as a
  `MediaType.MUSIC` `Work`; the play time is ephemeral runtime state in
  `extra["played_at"]`, not catalogue identity (axiom A3).

## Quick start

```python
from radiosoma import get_stations

for station in get_stations():
    print(station.title, station.best_stream)
    for variant in station.stream_variants:
        print(" ", variant.format, variant.bitrate, variant.url)
```

## Convert to mediavocab

### One Release per stream variant

```python
from radiosoma import get_stations
from radiosoma.converters import station_to_releases

jazz = next(s for s in get_stations() if s.station_id == "groovesalad")

for release in station_to_releases(jazz):
    print(release.codec, release.bitrate, release.uri)
    # e.g.  aac    130  https://somafm.com/groovesalad130.pls
    #       mp3    256  https://somafm.com/groovesalad256.pls
    #       he-aac  64  https://somafm.com/groovesalad64.pls
    #       he-aac  32  https://somafm.com/groovesalad32.pls
```

All releases share the same underlying `Work` so consumers can
deduplicate by identity. The `Work` carries `broadcaster_country="US"`
(the RADIO country slot; read it via `work.country`), `language="en"`,
`media_type=RADIO`, and `content_genres` resolved against
`mediavocab.taxonomy.genre.GENRE_*` constants where possible.

### Highest-quality release only

```python
from radiosoma.converters import station_to_release

release = station_to_release(jazz)
print(release.work.title)             # "Groove Salad"
print(release.codec, release.bitrate) # "aac" "130"
print(release.audio_channels)         # "stereo"
print(release.work.content_genres)    # [GENRE_AMBIENT]
```

## Now-playing / recent tracks

```python
from radiosoma import get_recent_tracks, get_stations
from radiosoma.converters import recent_tracks_to_works

jazz = next(s for s in get_stations() if s.station_id == "groovesalad")
songs = get_recent_tracks("groovesalad")

for work in recent_tracks_to_works(songs, jazz)[:3]:
    artist = work.credits[0].entity.name if work.credits else ""
    print(work.extra["played_at"], f"{artist} — {work.title}")
    print(work.extra.get("album", ""))
```

## Provider modality axis

```python
from radiosoma.converters import MODALITY
from mediavocab import PlaybackType

assert MODALITY == {PlaybackType.AUDIO}
```

## HTTP transport

`radiosoma` uses `requests` by default, but the HTTP session is
pluggable for consistency with sibling API clients in the family.

You can inject your own session:

```python
import requests
from radiosoma import get_stations, get_recent_tracks

sess = requests.Session()
sess.headers.update({"User-Agent": "my-app/1.0"})

for station in get_stations(session=sess):
    ...

tracks = get_recent_tracks("groovesalad", session=sess)
```

`SomaFmStation(raw, session=...)` likewise accepts an injected session.

To opt in to a `curl_cffi` browser-impersonating session, install the
optional extra and set the env var:

```bash
pip install radiosoma[stealth]
export RADIOSOMA_TRANSPORT=curl_cffi
```

SomaFM is an open API and does not need stealth transport. This option
exists only for parity across the api_clients family.

## Docs

- [API reference](docs/api.md)

## Examples

- [`examples/list_stations.py`](examples/list_stations.py): list every
  SOMA channel with all stream variants.
- [`examples/find_station.py`](examples/find_station.py): search by
  title, genre, or description.
- [`examples/mediavocab_jazz.py`](examples/mediavocab_jazz.py): mediavocab
  demo with multiple `Release`s per channel and recent tracks as `MUSIC`
  Works.

## Related projects

- [mediavocab](https://github.com/TigreGotico/mediavocab): the media
  vocabulary that defines `Work`, `Release`, and the other types this
  library converts SOMA FM data into.

## License

Apache-2.0. See [LICENSE](LICENSE).
