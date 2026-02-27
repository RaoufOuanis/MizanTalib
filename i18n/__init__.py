from __future__ import annotations

import gettext
from pathlib import Path
from typing import Iterable

_DOMAIN = "mizan_talib"
_LOCALE_DIR = Path(__file__).resolve().parent / "locale"
_FALLBACK_LANGUAGE = "ar"

_translation: gettext.NullTranslations = gettext.NullTranslations()
_current_language = _FALLBACK_LANGUAGE


def _load_translation(language: str | None) -> gettext.NullTranslations:
    if not language:
        return gettext.translation(
            _DOMAIN,
            localedir=_LOCALE_DIR,
            languages=[_FALLBACK_LANGUAGE],
            fallback=True,
        )
    try:
        return gettext.translation(
            _DOMAIN,
            localedir=_LOCALE_DIR,
            languages=[language],
        )
    except FileNotFoundError:
        return gettext.translation(
            _DOMAIN,
            localedir=_LOCALE_DIR,
            languages=[_FALLBACK_LANGUAGE],
            fallback=True,
        )


def set_language(language: str | None) -> str:
    global _translation, _current_language
    translation = _load_translation(language)
    _translation = translation
    _current_language = language or _FALLBACK_LANGUAGE
    return _current_language


def get_language() -> str:
    return _current_language


def gettext_(message: str) -> str:
    return _translation.gettext(message)


def ngettext_(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


def available_languages() -> list[str]:
    if not _LOCALE_DIR.exists():
        return [_FALLBACK_LANGUAGE]
    langs: list[str] = []
    for entry in _LOCALE_DIR.iterdir():
        mo_path = entry / "LC_MESSAGES" / f"{_DOMAIN}.mo"
        if mo_path.exists():
            langs.append(entry.name)
    return sorted(set(langs) | {_FALLBACK_LANGUAGE})


def install(language: str | None = None) -> None:
    active = set_language(language)
    gettext.bindtextdomain(_DOMAIN, str(_LOCALE_DIR))
    gettext.textdomain(_DOMAIN)
    if active:
        _translation.install()


def translate_many(messages: Iterable[str]) -> list[str]:
    return [gettext_(text) for text in messages]
