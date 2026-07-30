"""List all SomaFM stations with their stream variants."""
from radiosoma import get_stations

for station in get_stations():
    print(f"{station.title} [{station.genre}]")
    for v in station.stream_variants:
        print(f"  {v.source:>10}  {v.format:>4} {v.bitrate:>4}kbps  {v.url}")
    print()
