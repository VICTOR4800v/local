"""
Servizi esterni per la GUI (meteo e news), entrambi tramite API/feed
pubblici che NON richiedono alcuna API key:

- Meteo: Open-Meteo (https://open-meteo.com) - gratuita, no auth.
- News: feed RSS pubblico di Google News (nessuna auth, nessuna quota).

Queste chiamate sono bloccanti (rete): vanno sempre eseguite in un
thread separato dalla GUI (vedi gui/app.py -> _refresh_weather/_refresh_news).
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

WEATHER_CODES = {
    0: "Sereno", 1: "Poco nuvoloso", 2: "Nuvoloso", 3: "Coperto",
    45: "Nebbia", 48: "Nebbia gelata", 51: "Pioggerella", 53: "Pioggerella",
    55: "Pioggerella intensa", 61: "Pioggia debole", 63: "Pioggia",
    65: "Pioggia forte", 71: "Neve debole", 73: "Neve", 75: "Neve forte",
    80: "Rovesci", 81: "Rovesci", 82: "Rovesci violenti",
    95: "Temporale", 96: "Temporale con grandine", 99: "Temporale forte",
}

# Icone stile "app meteo normale" (emoji, nessun asset esterno necessario)
WEATHER_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️", 51: "🌦️", 53: "🌦️", 55: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "🌧️", 71: "🌨️", 73: "🌨️", 75: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}

GIORNI_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def weather_label(code):
    return WEATHER_CODES.get(code, "N/D")


def weather_icon(code):
    return WEATHER_ICONS.get(code, "🌡️")


def get_weather(lat=41.0833, lon=14.5333, city="Moiano (BN)", forecast_days=5):
    """Meteo attuale + previsioni dei prossimi giorni (icona + temp max/min)."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current_weather=true"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min"
            "&timezone=auto"
        )
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        payload = r.json()
        cw = payload["current_weather"]

        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        codes = daily.get("weathercode", [])
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])

        forecast = []
        # dates[0] e' oggi: mostriamo i prossimi giorni escludendo oggi
        for date_str, code, hi, lo in list(zip(dates, codes, tmax, tmin))[1:forecast_days + 1]:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            forecast.append({
                "day": GIORNI_IT[d.weekday()],
                "icon": weather_icon(code),
                "label": weather_label(code),
                "temp_max": hi,
                "temp_min": lo,
            })

        return {
            "city": city,
            "temp": cw["temperature"],
            "wind": cw["windspeed"],
            "condition": weather_label(cw["weathercode"]),
            "icon": weather_icon(cw["weathercode"]),
            "forecast": forecast,
        }
    except Exception as e:
        return {"error": str(e)}


def get_news(limit=6):
    """Ultimi titoli di news tramite il feed RSS pubblico di Google News."""
    try:
        url = "https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall("./channel/item")[:limit]
        titles = [it.findtext("title") or "" for it in items]
        return titles if titles else ["Nessuna news disponibile."]
    except Exception as e:
        return [f"Errore news: {e}"]