"""Cassette-backed parser tests for the SomaFM client.

These tests replay real captured HTTP responses against the parser so
upstream XML/PLS changes surface as test failures rather than silent
empty results.

Re-record cassettes::

    pytest --vcr-record=all test/test_somafm_vcr.py

The nightly CI workflow runs without cassettes against live endpoints.
"""
from __future__ import annotations

import requests
import pytest

from mediavocab import MediaType, Release as MvRelease, StreamMode

from radiosoma import SomaFmStation, get_recent_tracks, get_stations
from radiosoma.converters import station_to_release, station_to_releases


pytestmark = pytest.mark.vcr


def _first(it):
    for x in it:
        return x
    return None


def test_get_stations_yields_typed_stations():
    """``get_stations`` parses channels.xml into ``SomaFmStation`` objs."""
    stations = list(get_stations())
    assert stations, "expected at least one channel"
    assert all(isinstance(s, SomaFmStation) for s in stations)
    # Every channel must carry an id and a title.
    assert all(s.station_id for s in stations)
    assert all(s.title for s in stations)


def test_get_stations_groovesalad_present_with_streams():
    """Groove Salad is SOMA's flagship channel and must always be in the
    directory with at least one stream variant exposed."""
    by_id = {s.station_id: s for s in get_stations()}
    gs = by_id.get("groovesalad")
    assert gs is not None, "groovesalad channel missing from channels.xml"
    assert gs.streams, "expected stream URLs"
    assert gs.best_stream
    assert gs.fastest_stream
    # Every stream variant should yield a known codec.
    for v in gs.stream_variants:
        assert v.url
        assert v.codec in ("aac", "he-aac", "mp3")
        assert v.bitrate.isdigit()


def test_station_to_release_produces_mediavocab_release():
    """``station_to_release`` against a real channel must yield a
    mediavocab Release with the expected axiom-8 shape (RADIO Work,
    CONTINUOUS stream)."""
    gs = next(s for s in get_stations() if s.station_id == "groovesalad")
    rel = station_to_release(gs)
    assert isinstance(rel, MvRelease)
    assert rel.work.media_type == MediaType.RADIO
    assert rel.stream_mode == StreamMode.CONTINUOUS
    assert rel.uri  # best_stream URL
    assert rel.work.external_ids.get("soma_fm_channel_id") == "groovesalad"
    assert rel.work.runtime is None  # continuous live broadcast


def test_station_to_releases_one_per_variant():
    gs = next(s for s in get_stations() if s.station_id == "groovesalad")
    releases = station_to_releases(gs)
    assert len(releases) == len(gs.stream_variants)
    assert all(isinstance(r, MvRelease) for r in releases)
    # All releases share the same Work title.
    assert len({r.work.title for r in releases}) == 1


def test_get_recent_tracks_returns_song_dicts():
    """``get_recent_tracks`` parses songs/<id>.xml into a list of dicts."""
    songs = get_recent_tracks("groovesalad")
    assert isinstance(songs, list)
    assert songs, "expected non-empty recent-tracks feed"
    first = songs[0]
    assert isinstance(first, dict)
    assert first.get("title")
    # ``date`` is a unix epoch timestamp string.
    assert str(first.get("date", "")).isdigit()


def test_pls_stream_resolution():
    """The best-stream URL points at a SOMA ``.pls`` playlist that
    resolves to one or more icecast endpoints (``File1=`` line)."""
    gs = next(s for s in get_stations() if s.station_id == "groovesalad")
    pls = requests.get(gs.best_stream).text
    assert "[playlist]" in pls.lower() or "File1=" in pls
    # At least one File= entry pointing at an http(s) icecast URL.
    assert "File1=http" in pls
