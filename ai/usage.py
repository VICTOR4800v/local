import json
import os
from datetime import date

USAGE_FILE = "config/usage.json"

_EMPTY = {"date": None, "requests": 0, "prompt_tokens": 0, "response_tokens": 0, "total_tokens": 0}


class UsageTracker:
    """
    Tiene traccia di richieste e token consumati sull'API Gemini, con reset
    automatico ad ogni nuovo giorno (le quote free di Google si resettano a
    mezzanotte Pacific Time; qui usiamo la data locale come approssimazione
    semplice, sufficiente per farsi un'idea del consumo giornaliero).

    Non è un limite imposto da JARVIS: è puramente informativo, per capire
    quanto ci si avvicina alla propria quota gratuita su Google AI Studio.
    """

    def __init__(self):
        self.data = self._load()

    def _load(self):
        today = date.today().isoformat()
        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("date") == today:
                    return d
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {**_EMPTY, "date": today}

    def _save(self):
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def add(self, usage_metadata):
        """Chiamato dopo ogni risposta di Gemini (usage_metadata puo' essere None)."""
        today = date.today().isoformat()
        if self.data.get("date") != today:
            self.data = {**_EMPTY, "date": today}

        self.data["requests"] += 1
        if usage_metadata is not None:
            self.data["prompt_tokens"] += getattr(usage_metadata, "prompt_token_count", 0) or 0
            self.data["response_tokens"] += getattr(usage_metadata, "candidates_token_count", 0) or 0
            self.data["total_tokens"] += getattr(usage_metadata, "total_token_count", 0) or 0
        self._save()

    def snapshot(self):
        return dict(self.data)