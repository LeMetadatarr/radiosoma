"""Offline unit tests covering parser branches, error paths, and
property builders not exercised by the cassette-backed tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from radiosoma import (
    SomaFmStation,
    StreamVariant,
    _parse_bitrate_from_url,
    _xml2dict,
    get_recent_tracks,
    get_stations,
)
from radiosoma.converters import (
    _epoch_to_iso,
    song_to_work,
)


# ---------------------------------------------------------------------------
# _xml2dict / _parse_bitrate_from_url helpers
# ---------------------------------------------------------------------------

def test_xml2dict_returns_empty_dict_on_malformed_xml():
    assert _xml2dict("<not-xml") == {}


def test_xml2dict_handles_xhtml_namespace_strip():
    out = _xml2dict('<root xmlns="http://www.w3.org/1999/xhtml"><a>1</a></root>')
    assert out == {"root": {"a": "1"}}


def test_parse_bitrate_empty_url_returns_empty():
    assert _parse_bitrate_from_url("") == ""


def test_parse_bitrate_legacy_default_for_unsuffixed_url():
    assert _parse_bitrate_from_url("https://somafm.com/foo.pls") == "128"


def test_parse_bitrate_extracts_trailing_digits():
    assert _parse_bitrate_from_url("https://somafm.com/groovesalad130.pls") == "130"


# ---------------------------------------------------------------------------
# StreamVariant repr
# ---------------------------------------------------------------------------

def test_stream_variant_repr():
    v = StreamVariant("https://x/y.pls", "aac", "128", "highestpls")
    r = repr(v)
    assert "StreamVariant" in r
    assert "aac" in r
    assert "128" in r


def test_stream_variant_codec_falls_through_for_unknown_format():
    v = StreamVariant("https://x", "weirdfmt", "0", "fastpls")
    assert v.codec == "weirdfmt"
    assert v.container == ""


def test_stream_variant_codec_empty_when_format_blank():
    v = StreamVariant("https://x", "", "0", "fastpls")
    assert v.codec == ""


# ---------------------------------------------------------------------------
# SomaFmStation properties: error / fallback paths
# ---------------------------------------------------------------------------

def test_station_title_falls_back_to_id():
    s = SomaFmStation({"id": "foo"})
    assert s.title == "foo"


def test_station_image_prefers_xlimage_then_largeimage_then_image():
    assert SomaFmStation({"image": "i", "largeimage": "L", "xlimage": "X"}).image == "X"
    assert SomaFmStation({"image": "i", "largeimage": "L"}).image == "L"
    assert SomaFmStation({"image": "i"}).image == "i"


def test_station_dj_non_string_returns_empty():
    assert SomaFmStation({"id": "x", "dj": {"weird": "dict"}}).dj == ""


def test_station_dj_missing_returns_empty():
    assert SomaFmStation({"id": "x"}).dj == ""


def test_station_listeners_invalid_returns_none():
    assert SomaFmStation({"id": "x", "listeners": "not-a-number"}).listeners is None


def test_station_listeners_missing_returns_none():
    assert SomaFmStation({"id": "x"}).listeners is None


def test_station_listeners_int_typed():
    assert SomaFmStation({"id": "x", "listeners": "42"}).listeners == 42


def test_station_last_playing_non_string_returns_empty():
    assert SomaFmStation({"id": "x", "lastPlaying": ["a", "b"]}).last_playing == ""


def test_station_last_playing_missing():
    assert SomaFmStation({"id": "x"}).last_playing == ""


def test_station_updated_int_parses():
    assert SomaFmStation({"id": "x", "updated": "1700000000"}).updated == 1700000000


def test_station_updated_missing_returns_none():
    assert SomaFmStation({"id": "x"}).updated is None


def test_station_updated_invalid_returns_none():
    assert SomaFmStation({"id": "x", "updated": "garbage"}).updated is None


def test_station_description_default_empty():
    assert SomaFmStation({"id": "x"}).description == ""


def test_station_genre_optional():
    assert SomaFmStation({"id": "x"}).genre is None


# ---------------------------------------------------------------------------
# Stream variants: skip non-dict and empty-url entries
# ---------------------------------------------------------------------------

def test_variants_skip_non_dict_entries():
    s = SomaFmStation({
        "id": "x",
        "highestpls": ["not-a-dict", {"format": "aac", "text": "https://x/130.pls"}],
    })
    variants = s.stream_variants
    assert len(variants) == 1
    assert variants[0].url == "https://x/130.pls"


def test_variants_skip_entries_without_url():
    s = SomaFmStation({
        "id": "x",
        "highestpls": [{"format": "aac"}, {"format": "aac", "text": ""}],
    })
    assert s.stream_variants == []


def test_station_no_streams_returns_empty():
    s = SomaFmStation({"id": "x", "title": "X"})
    assert s.streams == []
    assert s.best_stream is None
    assert s.fastest_stream is None


def test_station_no_aac_stream_only_mp3():
    s = SomaFmStation({
        "id": "x",
        "title": "X",
        "fastpls": {"format": "mp3", "text": "https://somafm.com/x128.pls"},
    })
    assert s.fastest_stream == "https://somafm.com/x128.pls"
    # best falls back via fastpls when highestpls missing
    assert s.best_stream == "https://somafm.com/x128.pls"


def test_station_fastest_falls_back_to_highest():
    s = SomaFmStation({
        "id": "x",
        "highestpls": {"format": "aac", "text": "https://somafm.com/x130.pls"},
    })
    # No fastpls → fastest_stream falls back to highestpls.
    assert s.fastest_stream == "https://somafm.com/x130.pls"


def test_station_fastest_falls_back_to_slow():
    s = SomaFmStation({
        "id": "x",
        "slowpls": {"format": "aacp", "text": "https://somafm.com/x32.pls"},
    })
    assert s.fastest_stream == "https://somafm.com/x32.pls"


# ---------------------------------------------------------------------------
# URL builder properties
# ---------------------------------------------------------------------------

def test_m3u_stream_url():
    assert SomaFmStation({"id": "groovesalad"}).m3u_stream == \
        "http://somafm.com/m3u/groovesalad.m3u"


def test_direct_stream_url():
    assert SomaFmStation({"id": "groovesalad"}).direct_stream == \
        "http://ice2.somafm.com/groovesalad-128-mp3"


def test_alt_direct_stream_url():
    assert SomaFmStation({"id": "groovesalad"}).alt_direct_stream == \
        "http://ice4.somafm.com/groovesalad-128-mp3"


def test_station_str_returns_fastest_or_empty():
    s = SomaFmStation({
        "id": "x",
        "fastpls": {"format": "mp3", "text": "https://somafm.com/x128.pls"},
    })
    assert str(s) == "https://somafm.com/x128.pls"


def test_station_str_empty_when_no_streams():
    assert str(SomaFmStation({"id": "x"})) == ""


def test_station_repr_contains_title_and_stream():
    s = SomaFmStation({
        "id": "x",
        "title": "Xtitle",
        "fastpls": {"format": "mp3", "text": "https://somafm.com/x.pls"},
    })
    assert repr(s) == "Xtitle:https://somafm.com/x.pls"


# ---------------------------------------------------------------------------
# get_stations / get_recent_tracks: dict-vs-list coercion + malformed
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, text):
        self.text = text


def test_get_stations_handles_single_channel_dict():
    """When channels.xml has a single <channel> entry the parser yields
    a dict (not a list); ensure get_stations coerces it to a list."""
    xml = (
        "<channels>"
        "<channel id='only'><title>Only</title></channel>"
        "</channels>"
    )
    with patch("radiosoma.default_session", return_value=MagicMock(get=MagicMock(return_value=_FakeResp(xml)))):
        stations = list(get_stations())
    assert len(stations) == 1
    assert stations[0].station_id == "only"


def test_get_stations_handles_multiple_channels():
    xml = (
        "<channels>"
        "<channel id='a'><title>A</title></channel>"
        "<channel id='b'><title>B</title></channel>"
        "</channels>"
    )
    with patch("radiosoma.default_session", return_value=MagicMock(get=MagicMock(return_value=_FakeResp(xml)))):
        stations = list(get_stations())
    assert {s.station_id for s in stations} == {"a", "b"}


def test_get_stations_malformed_xml_yields_empty():
    with patch("radiosoma.default_session", return_value=MagicMock(get=MagicMock(return_value=_FakeResp("<not valid")))):
        assert list(get_stations()) == []


def test_get_recent_tracks_handles_single_song_dict():
    xml = (
        "<songs>"
        "<song><title>Solo</title><artist>X</artist><date>1700000000</date></song>"
        "</songs>"
    )
    with patch("radiosoma.default_session", return_value=MagicMock(get=MagicMock(return_value=_FakeResp(xml)))):
        songs = get_recent_tracks("foo")
    assert len(songs) == 1
    assert songs[0]["title"] == "Solo"


def test_get_recent_tracks_handles_empty_feed():
    xml = "<songs></songs>"
    with patch("radiosoma.default_session", return_value=MagicMock(get=MagicMock(return_value=_FakeResp(xml)))):
        assert get_recent_tracks("foo") == []


# ---------------------------------------------------------------------------
# converters: _epoch_to_iso edge cases + albumart
# ---------------------------------------------------------------------------

def test_epoch_to_iso_none_returns_none():
    assert _epoch_to_iso(None) is None


def test_epoch_to_iso_empty_string_returns_none():
    assert _epoch_to_iso("") is None


def test_epoch_to_iso_invalid_returns_none():
    assert _epoch_to_iso("not-a-number") is None


def test_epoch_to_iso_valid_returns_iso():
    out = _epoch_to_iso("1700000000")
    assert out is not None
    assert out.startswith("20")


def test_song_to_work_albumart_propagates():
    station = SomaFmStation({"id": "groovesalad", "title": "Groove Salad"})
    song = {
        "title": "Song",
        "artist": "Artist",
        "albumart": "https://somafm.com/img/song.jpg",
        "date": "1700000000",
    }
    work = song_to_work(song, station)
    assert work is not None
    assert work.extra["albumart"] == "https://somafm.com/img/song.jpg"


def test_song_to_work_uses_now_when_date_missing():
    station = SomaFmStation({"id": "groovesalad", "title": "Groove Salad"})
    work = song_to_work({"title": "Song"}, station)
    assert work is not None
    # Falls back to current wall clock — must still be ISO-formatted.
    assert work.extra["played_at"].startswith("20")


def test_song_to_work_no_artist_uses_title_only():
    station = SomaFmStation({"id": "groovesalad", "title": "Groove Salad"})
    work = song_to_work({"title": "Solo"}, station)
    assert work is not None
    assert work.title == "Solo"
    assert work.credits == []
