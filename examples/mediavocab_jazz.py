"""Rich mediavocab demo: fetch the Groove Salad channel, emit one
``Release`` per stream variant and the recent tracks as ``MUSIC`` Works."""
from radiosoma import get_recent_tracks, get_stations
from radiosoma.converters import (
    recent_tracks_to_works,
    station_to_releases,
)

# Pick a known channel — Groove Salad (downtempo/ambient).
station = next(s for s in get_stations() if s.station_id == "groovesalad")

print(f"Channel: {station.title} [{station.genre}]")
print(f"DJ:      {station.dj}")
print(f"Listeners: {station.listeners}")
print()

# One Release per bitrate/codec variant. All share the same Work.
print("Releases (one per stream variant):")
releases = station_to_releases(station)
for r in releases:
    print(
        f"  codec={r.codec:<7} bitrate={r.bitrate:>4}kbps "
        f"container={r.container:<5} uri={r.uri}"
    )
print(f"  content_genres={releases[0].work.content_genres}")
print(f"  country={releases[0].work.country} language={releases[0].work.language}")
print(f"  runtime={releases[0].work.runtime}  (None = continuous live)")
print()

# Recent-tracks feed → one MUSIC Work per recently-played song.
songs = get_recent_tracks(station.station_id)
tracks = recent_tracks_to_works(songs, station)
print(f"Recent tracks ({len(tracks)} MUSIC Works):")
for work in tracks[:5]:
    artist = work.credits[0].entity.name if work.credits else ""
    print(
        f"  {work.extra.get('played_at', '')}  {artist} — {work.title}  "
        f"album={work.extra.get('album', '')!r}"
    )
