"""Offline unit tests for ``radiosoma.converters``."""
from __future__ import annotations

from mediavocab import MediaType, StreamMode
from mediavocab.taxonomy import PlaybackType, RelationRole
from mediavocab.taxonomy import genre as _genre

from radiosoma import SomaFmStation
from radiosoma.converters import (
    MODALITY,
    recent_tracks_to_works,
    song_to_work,
    station_to_release,
    station_to_releases,
)


def _station(**overrides):
    raw = dict(
        id="groovesalad",
        title="Groove Salad",
        description="A nicely chilled plate of ambient/downtempo beats and grooves.",
        genre="ambient,downtempo",
        xlimage="https://somafm.com/img/groovesalad-large.jpg",
        highestpls={"format": "aac", "text": "https://somafm.com/groovesalad130.pls"},
        fastpls=[
            {"format": "mp3", "text": "https://somafm.com/groovesalad256.pls"},
            {"format": "aacp", "text": "https://somafm.com/groovesalad64.pls"},
        ],
        slowpls={"format": "aacp", "text": "https://somafm.com/groovesalad32.pls"},
        listeners="421",
        dj="Rusty Hodge",
        lastPlaying="Foo - Bar",
    )
    raw.update(overrides)
    return SomaFmStation(raw)


def test_modality_is_audio_only():
    assert MODALITY == {PlaybackType.AUDIO}


def test_to_release_uses_radio_media_type():
    rel = station_to_release(_station())
    assert rel.work.media_type == MediaType.RADIO


def test_to_release_uses_continuous_stream_mode():
    rel = station_to_release(_station())
    assert rel.stream_mode == StreamMode.CONTINUOUS


def test_to_release_uri_prefers_highestpls():
    rel = station_to_release(_station())
    # highestpls AAC 130 wins over the fastpls MP3 256 for "best".
    assert rel.uri == "https://somafm.com/groovesalad130.pls"


def test_to_release_carries_image():
    rel = station_to_release(_station())
    assert rel.image == "https://somafm.com/img/groovesalad-large.jpg"


def test_to_release_external_ids_use_soma_fm_channel_id():
    rel = station_to_release(_station())
    assert rel.work.external_ids.get("soma_fm_channel_id") == "groovesalad"
    assert rel.external_ids.get("soma_fm_channel_id") == "groovesalad"


def test_to_release_channel_id_is_string_typed():
    rel = station_to_release(_station(id=12345))
    assert rel.work.external_ids["soma_fm_channel_id"] == "12345"
    assert isinstance(rel.work.external_ids["soma_fm_channel_id"], str)


def test_to_release_country_and_language_are_us_english():
    rel = station_to_release(_station())
    assert rel.work.country == "US"
    assert rel.work.language == "en"


def test_to_release_runtime_is_none_for_continuous():
    rel = station_to_release(_station())
    assert rel.work.runtime is None


def test_to_release_genre_resolved_to_canonical_constants():
    rel = station_to_release(_station(genre="ambient,downtempo,chillout"))
    # all three SOMA tags collapse to GENRE_AMBIENT (deduplicated).
    assert rel.work.content_genres == [_genre.GENRE_AMBIENT]


def test_to_release_genre_pipe_separator():
    rel = station_to_release(_station(genre="electronic|specials"))
    assert _genre.GENRE_ELECTRONIC in rel.work.content_genres
    # unmapped tag falls through as raw lower-case string.
    assert "specials" in rel.work.content_genres


def test_to_release_genre_list_passed_through():
    rel = station_to_release(_station(genre=["Ambient", "Rock"]))
    assert _genre.GENRE_AMBIENT in rel.work.content_genres
    assert _genre.GENRE_ROCK in rel.work.content_genres


def test_to_release_codec_and_bitrate_populated():
    rel = station_to_release(_station())
    # highestpls is AAC at 130 kbps.
    assert rel.codec == "aac"
    assert rel.bitrate == "130"
    assert rel.container == "adts"
    assert rel.audio_channels == "stereo"


def test_to_releases_returns_one_per_variant():
    releases = station_to_releases(_station())
    assert len(releases) == 4
    # All share the same Work title.
    assert {r.work.title for r in releases} == {"Groove Salad"}
    # Distinct URIs per variant.
    uris = [r.uri for r in releases]
    assert len(set(uris)) == 4


def test_to_releases_codecs_and_bitrates():
    releases = station_to_releases(_station())
    by_uri = {r.uri.rsplit("/", 1)[-1]: r for r in releases}
    assert by_uri["groovesalad130.pls"].codec == "aac"
    assert by_uri["groovesalad130.pls"].bitrate == "130"
    assert by_uri["groovesalad256.pls"].codec == "mp3"
    assert by_uri["groovesalad256.pls"].bitrate == "256"
    assert by_uri["groovesalad64.pls"].codec == "he-aac"
    assert by_uri["groovesalad64.pls"].bitrate == "64"
    assert by_uri["groovesalad32.pls"].codec == "he-aac"
    assert by_uri["groovesalad32.pls"].bitrate == "32"


def test_to_releases_legacy_default_bitrate():
    # ``foo.pls`` (no numeric suffix) → SOMA's legacy 128 kbps MP3.
    station = SomaFmStation({
        "id": "foo",
        "title": "Foo",
        "fastpls": {"format": "mp3", "text": "https://somafm.com/foo.pls"},
    })
    releases = station_to_releases(station)
    assert len(releases) == 1
    assert releases[0].bitrate == "128"
    assert releases[0].codec == "mp3"


def test_to_release_handles_missing_optional_fields():
    bare = SomaFmStation({"id": "secretagent", "title": "Secret Agent"})
    rel = station_to_release(bare)
    assert rel.work.title == "Secret Agent"
    assert rel.work.media_type == MediaType.RADIO
    assert rel.work.content_genres == []
    assert rel.uri == ""


def test_to_release_handles_single_dict_highestpls():
    # Regression: when the XML scraper returns a single dict (not a
    # list) for ``highestpls``, the highest-quality stream must still
    # be discoverable.
    station = SomaFmStation({
        "id": "x",
        "title": "X",
        "highestpls": {"format": "aac", "text": "https://somafm.com/x130.pls"},
    })
    rel = station_to_release(station)
    assert rel.uri == "https://somafm.com/x130.pls"
    assert rel.codec == "aac"


def test_song_to_work_basic():
    station = _station()
    song = {
        "title": "Luminis",
        "artist": "Luis Junior",
        "album": "Urban Woman .01",
        "date": "1778114640",
    }
    work = song_to_work(song, station)
    assert work is not None
    assert work.media_type == MediaType.MUSIC
    assert work.title == "Luminis"
    assert len(work.credits) == 1
    assert work.credits[0].entity.name == "Luis Junior"
    assert work.credits[0].relation_role == RelationRole.PERFORMER
    assert work.extra["album"] == "Urban Woman .01"
    assert work.extra["soma_fm_channel_id"] == "groovesalad"
    # played_at is an ISO datetime (ephemeral runtime state).
    assert work.extra["played_at"].startswith("20")


def test_song_to_work_skips_empty_title():
    assert song_to_work({"title": "", "date": "1778114640"}, _station()) is None


def test_song_to_work_no_artist_has_no_credits():
    work = song_to_work({"title": "Solo", "date": "1778114640"}, _station())
    assert work is not None
    assert work.credits == []


def test_recent_tracks_to_works_filters_empty():
    station = _station()
    songs = [
        {"title": "A", "artist": "X", "date": "1778114640"},
        {"title": "", "artist": "", "date": "1778114000"},
        {"title": "B", "artist": "Y", "date": "1778113000"},
    ]
    works = recent_tracks_to_works(songs, station)
    assert len(works) == 2
    assert works[0].title == "A"
    assert works[1].title == "B"
