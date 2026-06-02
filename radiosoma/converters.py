"""Converters from radiosoma models to mediavocab typed objects.

SOMA FM channels are modelled per mediavocab axiom 8:

* Each channel is a ``Work`` with ``MediaType.RADIO`` (live-linear broadcast).
* Each distinct stream encoding is a ``Release`` with
  ``StreamMode.CONTINUOUS``. SOMA exposes multiple bitrate/codec pairs
  per channel (e.g. 130 kbps AAC, 128 kbps MP3, 64 kbps HE-AAC,
  32 kbps HE-AAC); each is a separate ``Release`` of the same ``Work``.
* Audio-only providers declare ``modality = {PlaybackType.AUDIO}``.

Recent-tracks feeds (``https://somafm.com/songs/<id>.xml``) surface each
recently-played song as a ``MediaType.MUSIC`` ``Work`` (it has title +
artist identity); the play time is ephemeral runtime state and rides in
``extra["played_at"]``. There is no schedule/now-playing vocabulary type —
that is delivery-time state, not catalogue identity (axiom A3).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from mediavocab import (
    MediaType,
    Release as MvRelease,
    StreamMode,
    Work,
)
from mediavocab.models.entity import Credit, EntityKind, EntityRef
from mediavocab.taxonomy import PlaybackType, RelationRole
from mediavocab.taxonomy import genre as _genre

from radiosoma import SomaFmStation, StreamVariant


# Audio-only provider axis. Importable by consumers that need to reason
# about the provider modality without instantiating a converter.
MODALITY = {PlaybackType.AUDIO}


# Map SOMA's free-form ``<genre>`` tags to canonical
# ``mediavocab.taxonomy.genre.GENRE_*`` constants. SOMA tokens are
# separated by ``,`` and ``|``; tokens not present in this table fall
# through as raw lower-cased strings (per axiom 10.2 escape-hatch
# behaviour).
_GENRE_MAP = {
    "ambient": _genre.GENRE_AMBIENT,
    "downtempo": _genre.GENRE_AMBIENT,  # closest canonical match
    "chillout": _genre.GENRE_AMBIENT,
    "electronic": _genre.GENRE_ELECTRONIC,
    "electronica": _genre.GENRE_ELECTRONIC,
    "house": _genre.GENRE_HOUSE,
    "techno": _genre.GENRE_TECHNO,
    "trance": _genre.GENRE_TRANCE,
    "drum and bass": _genre.GENRE_DRUM_AND_BASS,
    "dnb": _genre.GENRE_DRUM_AND_BASS,
    "dubstep": _genre.GENRE_DUBSTEP,
    "indie": _genre.GENRE_INDIE,
    "alternative": _genre.GENRE_INDIE,
    "rock": _genre.GENRE_ROCK,
    "pop": _genre.GENRE_POP,
    "punk": _genre.GENRE_PUNK,
    "metal": _genre.GENRE_METAL,
    "jazz": _genre.GENRE_JAZZ,
    "blues": _genre.GENRE_BLUES,
    "soul": _genre.GENRE_SOUL,
    "funk": _genre.GENRE_FUNK,
    "rnb": _genre.GENRE_RNB,
    "r&b": _genre.GENRE_RNB,
    "reggae": _genre.GENRE_REGGAE,
    "country": _genre.GENRE_COUNTRY,
    "americana": _genre.GENRE_FOLK,
    "folk": _genre.GENRE_FOLK,
    "classical": _genre.GENRE_CLASSICAL,
    "hip hop": _genre.GENRE_HIP_HOP,
    "hip-hop": _genre.GENRE_HIP_HOP,
    "hiphop": _genre.GENRE_HIP_HOP,
    "rap": _genre.GENRE_HIP_HOP,
    "world": _genre.GENRE_LATIN,  # SOMA "world" tag is closest to latin/world music
    "latin": _genre.GENRE_LATIN,
    "disco": _genre.GENRE_DISCO,
    "comedy": _genre.GENRE_COMEDY,
    # "news" / "talk" are broadcast formats, not genres (T1) — SOMA has no
    # such channels; an unknown tag falls through as a raw lower-cased string.
    "spoken word": _genre.GENRE_SPOKEN_WORD,
    "drone": _genre.GENRE_AMBIENT,
    "experimental": _genre.GENRE_AMBIENT,
}


def _normalise_genres(raw) -> List[str]:
    """Tokenise SOMA's free-form genre string and resolve canonical
    constants where possible."""
    if not raw:
        return []
    if isinstance(raw, list):
        tokens = [str(g).strip().lower() for g in raw if g]
    else:
        # SOMA uses both "," and "|" as separators.
        tokens = []
        for sep in ("|", ","):
            raw = str(raw).replace(sep, "\n")
        for tok in str(raw).split("\n"):
            tok = tok.strip().lower()
            if tok:
                tokens.append(tok)
    out: List[str] = []
    seen = set()
    for tok in tokens:
        canonical = _GENRE_MAP.get(tok, tok)
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def _epoch_to_iso(value) -> Optional[str]:
    """Validate a unix epoch (seconds, str or int) as an ISO datetime
    string with UTC offset, suitable for mediavocab's ``IsoDate`` type."""
    if value is None or value == "":
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _station_work(station: SomaFmStation) -> Work:
    """Build the canonical ``Work`` for a SOMA channel."""
    extra: dict = {}
    if station.streams:
        extra["stream_urls"] = station.streams
    if station.description:
        extra["description"] = station.description
    if station.dj:
        extra["dj"] = station.dj
    if station.listeners is not None:
        extra["listeners"] = str(station.listeners)
    if station.last_playing:
        extra["last_playing"] = station.last_playing

    external_ids: dict = {}
    if station.station_id:
        external_ids["soma_fm_channel_id"] = str(station.station_id)

    return Work(
        title=station.title,
        media_type=MediaType.RADIO,
        broadcaster_country="US",   # RADIO country slot (COUNTRY_SLOT_FOR)
        language="en",
        # ``runtime`` is intentionally omitted (None): a continuous live
        # broadcast has no finite duration.
        content_genres=_normalise_genres(station.genre),
        external_ids=dict(external_ids),
        extra=extra,
    )


def _variant_to_release(
    work: Work,
    station: SomaFmStation,
    variant: StreamVariant,
) -> MvRelease:
    external_ids: dict = {}
    if station.station_id:
        external_ids["soma_fm_channel_id"] = str(station.station_id)
    extra: dict = {
        "soma_pls_source": variant.source,
    }
    if variant.format:
        extra["soma_format"] = variant.format
    return MvRelease(
        work=work,
        uri=variant.url,
        image=station.image or "",
        stream_mode=StreamMode.CONTINUOUS,
        codec=variant.codec,
        container=variant.container,
        bitrate=variant.bitrate,
        audio_channels="stereo",
        audio_language="en",
        external_ids=external_ids,
        extra=extra,
    )


def station_to_release(station: SomaFmStation) -> MvRelease:
    """Convert a :class:`SomaFmStation` to a single mediavocab
    :class:`Release` wrapping the highest-quality stream.

    For the full set of bitrate/codec variants use
    :func:`station_to_releases`.
    """
    work = _station_work(station)
    variants = station.stream_variants
    if not variants:
        # Build an empty release so callers always get a valid object.
        return MvRelease(
            work=work,
            uri="",
            image=station.image or "",
            stream_mode=StreamMode.CONTINUOUS,
            audio_channels="stereo",
            audio_language="en",
            external_ids={
                "soma_fm_channel_id": str(station.station_id)
            } if station.station_id else {},
        )
    return _variant_to_release(work, station, variants[0])


def station_to_releases(station: SomaFmStation) -> List[MvRelease]:
    """Return one :class:`Release` per stream variant.

    Per axiom 8 each distinct codec/bitrate encoding is a different
    ``Release`` of the same ``Work``; SOMA exposes 4 such variants
    per channel (high-quality AAC, MP3, low-bitrate HE-AAC, lo-fi
    HE-AAC). All releases share the same underlying ``Work`` instance
    so consumers can deduplicate by identity.
    """
    work = _station_work(station)
    return [_variant_to_release(work, station, v) for v in station.stream_variants]


def song_to_work(
    song: dict,
    station: SomaFmStation,
) -> Optional[Work]:
    """Convert a recent-tracks entry to a ``MediaType.MUSIC`` :class:`Work`.

    ``song`` is a raw dict scraped from ``https://somafm.com/songs/<id>.xml``
    with keys ``title``, ``artist``, ``album``, ``date`` (unix epoch as str).
    Returns ``None`` if the entry has no title.

    The song's artist becomes a ``PERFORMER`` :class:`Credit`. The play time
    (ephemeral runtime state), album art, and the channel it aired on ride in
    ``extra`` — they are not catalogue identity (axiom A3).
    """
    title = (song.get("title") or "").strip()
    if not title:
        return None

    artist = (song.get("artist") or "").strip()
    album = (song.get("album") or "").strip()

    credits: List[Credit] = []
    if artist:
        credits.append(Credit(
            entity=EntityRef(name=artist, kind=EntityKind.GROUP),
            relation_role=RelationRole.PERFORMER,
        ))

    extra: dict = {
        "played_at": _epoch_to_iso(song.get("date"))
        or datetime.now(tz=timezone.utc).isoformat(),
    }
    if album:
        extra["album"] = album
    if song.get("albumart"):
        extra["albumart"] = str(song["albumart"])
    if station.station_id:
        extra["soma_fm_channel_id"] = str(station.station_id)

    return Work(
        title=title,
        media_type=MediaType.MUSIC,
        credits=credits,
        extra=extra,
    )


def recent_tracks_to_works(
    songs: list,
    station: SomaFmStation,
) -> List[Work]:
    """Map a recent-tracks feed to a list of ``MediaType.MUSIC`` Works,
    most-recent first (SOMA's source order). Entries with no title are
    skipped."""
    out: List[Work] = []
    for s in songs or []:
        work = song_to_work(s, station)
        if work is not None:
            out.append(work)
    return out
