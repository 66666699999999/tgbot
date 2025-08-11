# src/telegram_bot/localization/i18n.py

import json
import os

from telegram_bot.config import JSON_DIR


class I18n:
    _locales = {}

    @classmethod
    def load_locales(cls):
        """Load all locale files from the 'locales' directory."""
        path = os.path.join(JSON_DIR, "lang.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cls._locales = json.load(f)

    @classmethod
    def t(cls, lang: str, key_path: str, **kwargs) -> str:
        """Translate the given key for the specified language."""
        if not cls._locales:
            cls.load_locales()

        if lang not in cls._locales:
            lang = "zh"

        value = cls._locales.get(lang, {})
        for key in key_path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return key_path
            if value is None:
                return key_path  # fallback
        if isinstance(value, str):
            try:
                return value.format(**kwargs)
            except Exception:
                return value
        return value
