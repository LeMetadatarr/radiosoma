from collections import defaultdict
from typing import Iterable, List, Optional
from xml.etree import cElementTree as ET

from radiosoma.transport import default_session


def _etree2dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(_etree2dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {t.tag: {k: v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[t.tag].update((k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[t.tag]['text'] = text
        else:
            d[t.tag] = text
    return d


def _xml2dict(xml_string):
    try:
        xml_string = xml_string.replace('xmlns="http://www.w3.org/1999/xhtml"', "")
        e = ET.XML(xml_string)
        return _etree2dict(e)
    except Exception:
        return {}


def _as_list(value):
    """Normalise a field that can be a single dict or a list of dicts."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# Per SOMA FM convention the bitrate is embedded in the playlist filename
# (e.g. ``groovesalad130.pls`` → 130 kbps).  Where the playlist has no
# numeric suffix (e.g. ``groovesalad.pls``) SOMA serves the legacy 128 kbps
# MP3 stream.
_LEGACY_MP3_DEFAULT_BITRATE = "128"


def _parse_bitrate_from_url(url: str) -> str:
    """Extract a kbps figure from a SOMA playlist URL."""
    if not url:
        return ""
    # last path component, strip extension
    tail = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    digits = ""
    for ch in reversed(tail):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return digits or _LEGACY_MP3_DEFAULT_BITRATE


# Map SOMA's ``format`` attribute to canonical codec / container hints.
# ``aac`` is high-bitrate AAC-LC (in ADTS), ``aacp`` is HE-AAC v2 (lower
# bitrate, parametric stereo), ``mp3`` is MPEG-1 Layer 3.
_CODEC_BY_FORMAT = {
    "aac": "aac",
    "aacp": "he-aac",
    "mp3": "mp3",
}
_CONTAINER_BY_FORMAT = {
    "aac": "adts",
    "aacp": "adts",
    "mp3": "mp3",
}


class StreamVariant:
    """A single bitrate/codec offering for a SOMA channel."""

    __slots__ = ("url", "format", "bitrate", "source")

    def __init__(self, url: str, fmt: str, bitrate: str, source: str):
        self.url = url
        self.format = fmt
        self.bitrate = bitrate
        self.source = source  # "highestpls" | "fastpls" | "slowpls"

    @property
    def codec(self) -> str:
        return _CODEC_BY_FORMAT.get(self.format, self.format or "")

    @property
    def container(self) -> str:
        return _CONTAINER_BY_FORMAT.get(self.format, "")

    def __repr__(self) -> str:
        return f"StreamVariant({self.url!r}, {self.format!r}, {self.bitrate!r}kbps)"


class SomaFmStation:
    def __init__(self, raw, session=None):
        self.raw = raw
        self.session = session if session is not None else default_session()

    @property
    def station_id(self):
        return self.raw.get("id")

    @property
    def title(self):
        return self.raw.get("title") or self.raw.get("id")

    @property
    def image(self):
        return self.raw.get("xlimage") or \
               self.raw.get("largeimage") or \
               self.raw.get("image")

    @property
    def description(self):
        return self.raw.get("description", "")

    @property
    def genre(self):
        return self.raw.get("genre")

    @property
    def dj(self) -> str:
        v = self.raw.get("dj") or ""
        return v if isinstance(v, str) else ""

    @property
    def listeners(self) -> Optional[int]:
        v = self.raw.get("listeners")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def last_playing(self) -> str:
        v = self.raw.get("lastPlaying") or ""
        return v if isinstance(v, str) else ""

    @property
    def updated(self) -> Optional[int]:
        v = self.raw.get("updated")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    def _variants_for(self, key: str) -> List[StreamVariant]:
        out: List[StreamVariant] = []
        for entry in _as_list(self.raw.get(key)):
            if not isinstance(entry, dict):
                continue
            url = entry.get("text") or ""
            if not url:
                continue
            fmt = (entry.get("format") or "").lower()
            out.append(StreamVariant(
                url=url,
                fmt=fmt,
                bitrate=_parse_bitrate_from_url(url),
                source=key,
            ))
        return out

    @property
    def stream_variants(self) -> List[StreamVariant]:
        """All available stream variants in priority order:
        ``highestpls`` → ``fastpls`` → ``slowpls``."""
        return (
            self._variants_for("highestpls")
            + self._variants_for("fastpls")
            + self._variants_for("slowpls")
        )

    @property
    def streams(self):
        """All stream URLs (legacy API, kept for compatibility)."""
        return [v.url for v in self.stream_variants]

    @property
    def best_stream(self):
        """Highest-quality stream URL (first ``highestpls``, falling
        back to the first ``fastpls`` / ``slowpls``)."""
        variants = self.stream_variants
        return variants[0].url if variants else None

    @property
    def fastest_stream(self):
        """Lowest-latency stream URL (first ``fastpls``, falling back
        to ``highestpls`` / ``slowpls``)."""
        for key in ("fastpls", "highestpls", "slowpls"):
            for v in self._variants_for(key):
                return v.url
        return None

    @property
    def m3u_stream(self):
        return f"http://somafm.com/m3u/{self.station_id}.m3u"

    @property
    def direct_stream(self):
        return f"http://ice2.somafm.com/{self.station_id}-128-mp3"

    @property
    def alt_direct_stream(self):
        return f"http://ice4.somafm.com/{self.station_id}-128-mp3"

    def __str__(self):
        return self.fastest_stream or ""

    def __repr__(self):
        return self.title + ":" + str(self)


def get_stations(session=None) -> Iterable[SomaFmStation]:
    sess = session if session is not None else default_session()
    xml = sess.get("https://api.somafm.com/channels.xml").text
    data = _xml2dict(xml)
    channels = (data.get("channels") or {}).get("channel", []) or []
    if isinstance(channels, dict):
        channels = [channels]
    for channel in channels:
        yield SomaFmStation(channel, session=sess)


def get_recent_tracks(channel_id, session=None):
    """Fetch the recent-tracks feed for a SOMA FM channel.

    Returns a list of dicts (most recent first) with keys
    ``title``, ``artist``, ``album``, ``albumart``, ``date``.
    """
    sess = session if session is not None else default_session()
    url = f"https://somafm.com/songs/{channel_id}.xml"
    xml = sess.get(url).text
    data = _xml2dict(xml)
    songs = (data.get("songs") or {}).get("song", []) or []
    if isinstance(songs, dict):
        songs = [songs]
    return songs
