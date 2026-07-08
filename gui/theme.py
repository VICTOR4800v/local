"""
Design tokens dell'interfaccia JARVIS.

Direzione estetica: HUD tattico / cyberpunk. Monospace ovunque (richiesto
dal brief), duotone ciano + magenta (il classico accostamento sci-fi:
ciano = dati/sistema, magenta = azione/attenzione), sfondi quasi-neri con
tinta blu fredda invece del grigio neutro, e un solo motivo grafico
ricorrente (le "staffe" ad angolo, vedi widgets.HUDPanel) usato con
disciplina su tutti i pannelli principali invece di decorare ogni angolo
della UI in modo diverso.
"""

BG_DEEP = "#05070a"      # sfondo finestra: nero con tinta blu fredda
BG_PANEL = "#0d1117"     # pannelli principali
BG_PANEL_ALT = "#12171f" # elementi annidati (box upload, forecast, ecc.)
BG_INPUT = "#0a0e14"

CYAN = "#00F0FF"
CYAN_DIM = "#0a4a55"
MAGENTA = "#FF2E7A"
MAGENTA_DIM = "#5a1030"
AMBER = "#FFB020"
GREEN_OK = "#00F0FF"

TXT_BRIGHT = "#E7F6F8"
TXT_MAIN = "#c8d6d8"
TXT_DIM = "#5b6a70"

FONT_MAIN = ("JetBrains Mono", 13)
FONT_SMALL = ("JetBrains Mono", 11)
FONT_MICRO = ("JetBrains Mono", 10)
FONT_TITLE = ("JetBrains Mono", 25, "bold")
FONT_CLOCK = ("JetBrains Mono", 21, "bold")
FONT_LABEL = ("JetBrains Mono", 11, "bold")
FONT_EMOJI_SM = ("Segoe UI Emoji", 16)
FONT_EMOJI_LG = ("Segoe UI Emoji", 34)


def spaced(text: str) -> str:
    """'SISTEMA' -> 'S I S T E M A' — etichette di sezione stile terminale/HUD."""
    return " ".join(list(text))


def load_color(percent: float) -> str:
    """Colore dinamico per barre di carico: ciano -> ambra -> magenta."""
    if percent < 60:
        return CYAN
    if percent < 85:
        return AMBER
    return MAGENTA