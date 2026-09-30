"""Offline UI language packs; the upstream translator handles protocol messages."""
import json
from functools import lru_cache
from constants import _resource_path


@lru_cache(maxsize=1)
def catalogs():
    return json.loads(_resource_path("web/locales.json").read_text(encoding="utf-8"))


def language_options():
    return [{"name": name, "locale": pack["locale"]} for name, pack in catalogs().items()]


def text(value):
    from translate import _
    pack = catalogs().get(_.current, catalogs()["English"])
    return pack["messages"].get(value, value)
