"""
Widget riutilizzabili per la UI cyber-HUD di JARVIS.

HUDPanel e' il motivo grafico "firma" dell'interfaccia: un pannello con
staffe ad angolo (corner brackets) come nelle interfacce tattiche/sci-fi,
invece del solito rettangolo con bordo uniforme. E' semplicemente un
CTkFrame con 4 piccoli tk.Canvas ancorati sui suoi angoli (via place con
relx/rely + anchor, dimensione fissa): restano al loro posto qualunque
sia la dimensione del pannello, senza dover ridisegnare nulla al resize.
"""
import tkinter as tk
import customtkinter as ctk

from gui.theme import BG_PANEL, CYAN, CYAN_DIM, TXT_BRIGHT, FONT_SMALL, load_color

_CORNER_SPECS = {
    "nw": [(0, 0.62), (0, 0), (0.62, 0)],
    "ne": [(0.38, 0), (1, 0), (1, 0.62)],
    "sw": [(0, 0.38), (0, 1), (0.62, 1)],
    "se": [(0.38, 1), (1, 1), (1, 0.38)],
}


class HUDPanel(ctk.CTkFrame):
    def __init__(self, master, fg_color=BG_PANEL, accent=CYAN, corner_radius=10,
                 bracket=18, **kwargs):
        super().__init__(master, fg_color=fg_color, corner_radius=corner_radius,
                          border_width=1, border_color=CYAN_DIM, **kwargs)
        self.accent = accent
        self.bracket = bracket
        self._bg_hex = fg_color if isinstance(fg_color, str) else fg_color[-1]

        for anchor, pts in _CORNER_SPECS.items():
            relx = 0 if "w" in anchor else 1
            rely = 0 if "n" in anchor else 1
            c = tk.Canvas(self, width=bracket, height=bracket, bg=self._bg_hex,
                          highlightthickness=0)
            c.place(relx=relx, rely=rely, anchor=anchor)
            flat = []
            for px, py in pts:
                flat.extend([px * bracket, py * bracket])
            c.create_line(*flat, fill=accent, width=2)


class StatRow(ctk.CTkFrame):
    """Riga 'etichetta + barra + valore' con colore dinamico in base al carico."""

    def __init__(self, master, label, dynamic_color=True):
        super().__init__(master, fg_color="transparent")
        self.dynamic_color = dynamic_color
        self.label = ctk.CTkLabel(self, text=label, font=FONT_SMALL, text_color=CYAN,
                                   width=70, anchor="w")
        self.label.pack(side="left")
        self.bar = ctk.CTkProgressBar(self, progress_color=CYAN, fg_color="#1a2129", height=10)
        self.bar.set(0)
        self.bar.pack(side="left", fill="x", expand=True, padx=8)
        self.value_label = ctk.CTkLabel(self, text="--%", font=FONT_SMALL, text_color=TXT_BRIGHT,
                                         width=52, anchor="e")
        self.value_label.pack(side="left")

    def update_value(self, percent, text=None):
        self.bar.set(max(0.0, min(1.0, percent / 100.0)))
        if self.dynamic_color:
            self.bar.configure(progress_color=load_color(percent))
        self.value_label.configure(text=text or f"{percent:.0f}%")


class StatusDot(ctk.CTkFrame):
    """Pallino di stato + etichetta (idle/thinking/speaking), stile indicatore HUD."""

    STATE_COLORS = {
        "idle": "#4a5560",
        "thinking": "#FFB020",
        "speaking": CYAN,
    }

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.dot = ctk.CTkLabel(self, text="●", font=("JetBrains Mono", 14),
                                 text_color=self.STATE_COLORS["idle"])
        self.dot.pack(side="left", padx=(0, 6))
        self.text = ctk.CTkLabel(self, text="IDLE", font=FONT_SMALL, text_color="#8a97a0")
        self.text.pack(side="left")

    def set_state(self, state: str):
        color = self.STATE_COLORS.get(state, "#4a5560")
        self.dot.configure(text_color=color)
        self.text.configure(text=state.upper(), text_color=color)