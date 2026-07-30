"""Pluggable HTTP transport for radiosoma.

By default uses :class:`requests.Session`. If the environment variable
``RADIOSOMA_TRANSPORT`` is set to ``curl_cffi`` and the ``curl_cffi``
package is importable, a ``curl_cffi`` session impersonating a recent
Chrome browser is returned instead.

This is mostly here for consistency with sibling API clients in the
family — SomaFM is an open, friendly API and does not require stealth
transport, but adopting the same pattern everywhere keeps the surface
uniform.
"""
import os


def default_session():
    """Return a requests-compatible session.

    Honours ``RADIOSOMA_TRANSPORT=curl_cffi`` when ``curl_cffi`` is
    available; otherwise falls back to ``requests.Session``.
    """
    if os.environ.get("RADIOSOMA_TRANSPORT") == "curl_cffi":
        try:
            from curl_cffi import requests as curl_requests
            return curl_requests.Session(impersonate="chrome")
        except ImportError:
            pass
    import requests
    return requests.Session()
