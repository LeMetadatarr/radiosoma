"""Tests for pluggable HTTP transport."""
import sys
import types
from unittest.mock import MagicMock

import requests

import radiosoma
from radiosoma.transport import default_session


_CHANNELS_XML = """<?xml version="1.0"?>
<channels>
  <channel id="groovesalad">
    <title>Groove Salad</title>
    <fastpls format="aac">http://somafm.com/groovesalad130.pls</fastpls>
  </channel>
</channels>
"""

_SONGS_XML = """<?xml version="1.0"?>
<songs>
  <song>
    <title>Foo</title>
    <artist>Bar</artist>
  </song>
</songs>
"""


def _fake_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    sess.get.return_value = resp
    return sess


def test_get_stations_uses_injected_session():
    sess = _fake_session(_CHANNELS_XML)
    stations = list(radiosoma.get_stations(session=sess))
    sess.get.assert_called_once_with("https://api.somafm.com/channels.xml")
    assert len(stations) == 1
    assert stations[0].station_id == "groovesalad"
    # station inherits the injected session
    assert stations[0].session is sess


def test_get_recent_tracks_uses_injected_session():
    sess = _fake_session(_SONGS_XML)
    songs = radiosoma.get_recent_tracks("groovesalad", session=sess)
    sess.get.assert_called_once_with("https://somafm.com/songs/groovesalad.xml")
    assert len(songs) == 1


def test_station_default_session_is_requests():
    station = radiosoma.SomaFmStation({"id": "x"})
    assert isinstance(station.session, requests.Session)


def test_default_session_no_env_returns_requests(monkeypatch):
    monkeypatch.delenv("RADIOSOMA_TRANSPORT", raising=False)
    assert isinstance(default_session(), requests.Session)


def test_default_session_unknown_env_returns_requests(monkeypatch):
    monkeypatch.setenv("RADIOSOMA_TRANSPORT", "something_else")
    assert isinstance(default_session(), requests.Session)


def test_default_session_curl_cffi_when_unavailable_falls_back(monkeypatch):
    """If curl_cffi is requested but not importable, fall back to requests."""
    monkeypatch.setenv("RADIOSOMA_TRANSPORT", "curl_cffi")
    # ensure curl_cffi import fails
    monkeypatch.setitem(sys.modules, "curl_cffi", None)
    sess = default_session()
    assert isinstance(sess, requests.Session)


def test_default_session_curl_cffi_when_available(monkeypatch):
    """When curl_cffi is importable and env is set, use it."""
    monkeypatch.setenv("RADIOSOMA_TRANSPORT", "curl_cffi")

    fake_session_instance = object()
    fake_requests_module = types.SimpleNamespace(
        Session=MagicMock(return_value=fake_session_instance)
    )
    fake_curl_cffi = types.ModuleType("curl_cffi")
    fake_curl_cffi.requests = fake_requests_module
    monkeypatch.setitem(sys.modules, "curl_cffi", fake_curl_cffi)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", fake_requests_module)

    sess = default_session()
    assert sess is fake_session_instance
    fake_requests_module.Session.assert_called_once_with(impersonate="chrome")
