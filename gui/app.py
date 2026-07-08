import json
import os
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog
import psutil

from gui.hologram import HologramSphere
from gui.services import get_weather, get_news
from gui.widgets import HUDPanel, StatRow, StatusDot
from gui.theme import (
    BG_DEEP, BG_PANEL, BG_PANEL_ALT, BG_INPUT, CYAN, CYAN_DIM, MAGENTA, MAGENTA_DIM,
    TXT_BRIGHT, TXT_MAIN, TXT_DIM, FONT_MAIN, FONT_SMALL, FONT_MICRO, FONT_TITLE,
    FONT_CLOCK, FONT_LABEL, FONT_EMOJI_SM, FONT_EMOJI_LG, spaced,
)
from core.message_bus import MessageBus

NOTES_FILE = "config/notes.json"

MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def section_label(master, text, color=CYAN):
    return ctk.CTkLabel(master, text=spaced(text), font=FONT_LABEL, text_color=color, anchor="w")


class JarvisGUI(ctk.CTk):
    def __init__(self, bus: MessageBus):
        super().__init__()
        self.bus = bus

        ctk.set_appearance_mode("dark")
        self.title("JARVIS")
        self.geometry("1300x780")
        self.configure(fg_color=BG_DEEP)

        self.uploaded_file = None
        self._last_net = None
        self._build_layout()

        self.hologram.start()
        self._tick_clock()
        self._tick_hw_stats()
        self._refresh_weather()
        self._refresh_news()
        self._load_initial_usage()
        self.after(100, self.update_gui_from_bus)

    # ------------------------------------------------------------------ UI

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=400)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()
        self._build_footer()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=24, pady=(16, 4))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        title = ctk.CTkLabel(title_box, text=spaced("J.A.R.V.I.S."), font=FONT_TITLE, text_color=CYAN)
        title.pack(anchor="w")
        ctk.CTkLabel(title_box, text="SISTEMA DI ASSISTENZA COGNITIVA // v2",
                     font=FONT_MICRO, text_color=TXT_DIM).pack(anchor="w")

        clock_box = ctk.CTkFrame(header, fg_color="transparent")
        clock_box.grid(row=0, column=1, sticky="e")
        self.clock_label = ctk.CTkLabel(clock_box, text="--:--:--", font=FONT_CLOCK, text_color=CYAN)
        self.clock_label.pack(anchor="e")
        self.date_label = ctk.CTkLabel(clock_box, text="--", font=FONT_SMALL, text_color=TXT_DIM)
        self.date_label.pack(anchor="e")

        # "traccia circuito": linea d'accento con nodi, sotto l'header
        trace = tk.Canvas(self, height=6, bg=BG_DEEP, highlightthickness=0)
        trace.grid(row=0, column=0, columnspan=3, sticky="sew", padx=24, pady=(0, 6))
        self.after(50, lambda: self._draw_trace(trace))
        trace.bind("<Configure>", lambda e: self._draw_trace(trace))

    @staticmethod
    def _draw_trace(canvas):
        canvas.delete("all")
        w = max(canvas.winfo_width(), 1)
        canvas.create_line(0, 3, w, 3, fill=CYAN_DIM, width=1)
        canvas.create_oval(-3, 0, 3, 6, fill=CYAN, outline="")
        canvas.create_oval(w - 3, 0, w + 3, 6, fill=MAGENTA, outline="")

    def _build_left_panel(self):
        panel = HUDPanel(self, fg_color=BG_PANEL, accent=CYAN)
        panel.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=10)

        section_label(panel, "SISTEMA").pack(pady=(16, 10), padx=16, anchor="w")

        stats_box = ctk.CTkFrame(panel, fg_color="transparent")
        stats_box.pack(fill="x", padx=16)
        self.cpu_row = StatRow(stats_box, "CPU")
        self.cpu_row.pack(fill="x", pady=4)
        self.ram_row = StatRow(stats_box, "RAM")
        self.ram_row.pack(fill="x", pady=4)
        self.disk_row = StatRow(stats_box, "DISCO")
        self.disk_row.pack(fill="x", pady=4)
        self.net_row = StatRow(stats_box, "RETE", dynamic_color=False)
        self.net_row.pack(fill="x", pady=4)

        self._divider(panel)

        section_label(panel, "METEO").pack(padx=16, anchor="w")

        current_box = ctk.CTkFrame(panel, fg_color="transparent")
        current_box.pack(fill="x", padx=16, pady=(8, 8))

        self.weather_city_label = ctk.CTkLabel(current_box, text="Moiano (BN)", font=FONT_SMALL,
                                                 text_color=TXT_DIM, anchor="w")
        self.weather_city_label.pack(anchor="w")

        current_row = ctk.CTkFrame(current_box, fg_color="transparent")
        current_row.pack(fill="x", pady=(4, 0))

        self.weather_icon_label = ctk.CTkLabel(current_row, text="⏳", font=FONT_EMOJI_LG)
        self.weather_icon_label.pack(side="left", padx=(0, 10))

        temp_box = ctk.CTkFrame(current_row, fg_color="transparent")
        temp_box.pack(side="left")
        self.weather_temp_label = ctk.CTkLabel(temp_box, text="--°C", font=("JetBrains Mono", 21, "bold"),
                                                text_color=TXT_BRIGHT)
        self.weather_temp_label.pack(anchor="w")
        self.weather_cond_label = ctk.CTkLabel(temp_box, text="Caricamento...", font=FONT_MICRO,
                                                text_color=TXT_DIM)
        self.weather_cond_label.pack(anchor="w")

        self.forecast_box = ctk.CTkFrame(panel, fg_color=BG_PANEL_ALT, corner_radius=10,
                                          border_width=1, border_color="#1c2530")
        self.forecast_box.pack(fill="x", padx=16, pady=(2, 10))
        self.forecast_rows = []
        for _ in range(5):
            row = ctk.CTkFrame(self.forecast_box, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=4)
            day_lbl = ctk.CTkLabel(row, text="--", font=FONT_SMALL, text_color=TXT_MAIN, width=40, anchor="w")
            day_lbl.pack(side="left")
            icon_lbl = ctk.CTkLabel(row, text="", font=FONT_EMOJI_SM, width=30)
            icon_lbl.pack(side="left")
            temp_lbl = ctk.CTkLabel(row, text="--° / --°", font=FONT_SMALL, text_color=TXT_BRIGHT, anchor="e")
            temp_lbl.pack(side="right")
            self.forecast_rows.append((day_lbl, icon_lbl, temp_lbl))

        self._divider(panel)

        section_label(panel, "NEWS").pack(padx=16, anchor="w")
        self.news_box = ctk.CTkTextbox(panel, font=FONT_MICRO, fg_color="transparent",
                                        text_color=TXT_MAIN, wrap="word")
        self.news_box.pack(fill="both", expand=True, padx=16, pady=(6, 16))
        self.news_box.configure(state="disabled")

    @staticmethod
    def _divider(master):
        ctk.CTkFrame(master, fg_color=CYAN_DIM, height=1).pack(fill="x", padx=16, pady=12)

    def _build_center_panel(self):
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.hologram = HologramSphere(panel, size=380, color=CYAN, bg=BG_DEEP)
        self.hologram.grid(row=0, column=0)

        self.status_dot = StatusDot(panel)
        self.status_dot.grid(row=1, column=0, pady=(4, 10))

    def _build_right_panel(self):
        panel = HUDPanel(self, fg_color=BG_PANEL, accent=MAGENTA)
        panel.grid(row=1, column=2, sticky="nsew", padx=(12, 24), pady=10)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        section_label(panel, "COMUNICAZIONE", color=MAGENTA).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        self.text_display = ctk.CTkTextbox(panel, font=FONT_MAIN, fg_color="transparent",
                                            text_color=TXT_BRIGHT, wrap="word")
        self.text_display.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self.text_display.tag_config("tu_tag", foreground=MAGENTA)
        self.text_display.tag_config("jarvis_tag", foreground=CYAN)
        self.text_display.tag_config("ts", foreground=TXT_DIM)
        self.text_display.tag_config("body", foreground=TXT_BRIGHT)
        self.text_display.configure(state="disabled")

        input_frame = ctk.CTkFrame(panel, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        input_frame.grid_columnconfigure(0, weight=1)

        self.text_entry = ctk.CTkEntry(
            input_frame, font=FONT_MAIN, placeholder_text="> scrivi un comando...",
            fg_color=BG_INPUT, border_color=CYAN, text_color=TXT_BRIGHT,
        )
        self.text_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.text_entry.bind("<Return>", self.send_text_command)

        self.send_button = ctk.CTkButton(
            input_frame, text="INVIA", font=FONT_SMALL, fg_color=CYAN, text_color="#001014",
            hover_color="#5CFBFF", width=80, command=self.send_text_command,
        )
        self.send_button.grid(row=0, column=1)

        upload_frame = ctk.CTkFrame(panel, fg_color=BG_PANEL_ALT, corner_radius=10,
                                     border_width=1, border_color=MAGENTA_DIM)
        upload_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        upload_frame.grid_columnconfigure(1, weight=1)

        upload_btn = ctk.CTkButton(
            upload_frame, text="⇪ CARICA FILE", font=FONT_MICRO, fg_color="transparent",
            border_color=MAGENTA, border_width=1, text_color=MAGENTA, hover_color="#241019",
            width=120, command=self.upload_file,
        )
        upload_btn.grid(row=0, column=0, padx=10, pady=10)

        self.upload_label = ctk.CTkLabel(upload_frame, text="nessun file caricato", font=FONT_MICRO,
                                          text_color=TXT_DIM, anchor="w")
        self.upload_label.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        self.voice_button = ctk.CTkButton(
            upload_frame, text="🎙 VOCE LIVE", font=FONT_MICRO, fg_color="transparent",
            border_color=CYAN, border_width=1, text_color=CYAN, hover_color="#0a1a1f",
            width=120, command=lambda: self.bus.input_queue.put("__TOGGLE_LIVE_VOICE__"),
        )
        self.voice_button.grid(row=0, column=2, padx=(0, 10), pady=10)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=24, pady=(0, 16))

        self.notes_button = ctk.CTkButton(
            footer, text="🗒 NOTE", font=FONT_SMALL, fg_color=BG_PANEL_ALT, border_color=MAGENTA,
            border_width=1, text_color=MAGENTA, hover_color="#241019", width=120,
            command=self.open_notes,
        )
        self.notes_button.pack(side="left")

        right_box = ctk.CTkFrame(footer, fg_color="transparent")
        right_box.pack(side="right")

        # Monitor token/richieste Gemini: puramente informativo, per farsi
        # un'idea di quanto si consuma della quota gratuita giornaliera.
        self.usage_label = ctk.CTkLabel(
            right_box, text="TOKEN OGGI: -- · RICHIESTE: --", font=FONT_MICRO, text_color=TXT_DIM,
        )
        self.usage_label.pack(anchor="e")

        ctk.CTkLabel(right_box, text="J.A.R.V.I.S. // CORE ONLINE", font=FONT_MICRO,
                     text_color=TXT_DIM).pack(anchor="e")

    # ------------------------------------------------------------- Chat/IO

    def _append_chat(self, who, text, who_tag):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text_display.configure(state="normal")
        self.text_display.insert("end", f"{ts}  ", "ts")
        self.text_display.insert("end", f"{who} ", who_tag)
        self.text_display.insert("end", f"{text}\n\n", "body")
        self.text_display.configure(state="disabled")
        self.text_display.see("end")

    def send_text_command(self, event=None):
        text = self.text_entry.get().strip()
        if not text:
            return
        self._append_chat("TU >", text, "tu_tag")
        self.bus.input_queue.put(text)
        self.text_entry.delete(0, "end")

    def update_gui_from_bus(self):
        if not self.bus.gui_queue.empty():
            msg = self.bus.gui_queue.get()
            if msg["type"] == "text":
                self._append_chat("JARVIS >", msg["data"], "jarvis_tag")
            elif msg["type"] == "status":
                self.status_dot.set_state(msg["data"])
            elif msg["type"] == "speaking":
                self.hologram.set_speaking(bool(msg["data"]))
                if msg["data"]:
                    self.status_dot.set_state("speaking")
            elif msg["type"] == "usage":
                self._update_usage_label(msg["data"])
        self.after(100, self.update_gui_from_bus)

    def _update_usage_label(self, usage):
        total = usage.get("total_tokens", 0)
        requests = usage.get("requests", 0)
        self.usage_label.configure(text=f"TOKEN OGGI: {total:,} · RICHIESTE: {requests}".replace(",", "."))

    def upload_file(self):
        path = filedialog.askopenfilename(title="Seleziona un file da caricare")
        if not path:
            return
        self.uploaded_file = path
        filename = os.path.basename(path)
        self.upload_label.configure(text=filename, text_color=TXT_BRIGHT)
        self._append_chat("FILE >", path, "tu_tag")
        self.bus.input_queue.put(f"[Contesto: l'utente ha caricato il file '{path}']")

    # ------------------------------------------------------------- Orologio

    def _tick_clock(self):
        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        self.date_label.configure(text=f"{now.day} {MESI_IT[now.month - 1]} {now.year}")
        self.after(1000, self._tick_clock)

    # ------------------------------------------------------------- Hardware

    def _tick_hw_stats(self):
        psutil.cpu_percent(interval=None)
        threading.Thread(target=self._collect_hw_stats, daemon=True).start()
        self.after(2500, self._tick_hw_stats)

    def _collect_hw_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage(os.path.abspath(os.sep)).percent

            net = psutil.net_io_counters()
            now = datetime.now().timestamp()
            if self._last_net is not None:
                prev_net, prev_t = self._last_net
                elapsed = max(0.1, now - prev_t)
                bytes_delta = (net.bytes_sent + net.bytes_recv) - (prev_net.bytes_sent + prev_net.bytes_recv)
                kbps = max(0.0, bytes_delta / 1024.0 / elapsed)
            else:
                kbps = 0.0
            self._last_net = (net, now)
        except Exception:
            cpu = ram = disk = 0
            kbps = 0.0

        def apply():
            self.cpu_row.update_value(cpu)
            self.ram_row.update_value(ram)
            self.disk_row.update_value(disk)
            self.net_row.update_value(100, text=f"{kbps:.0f} KB/s")

        try:
            self.after(0, apply)
        except RuntimeError:
            pass  # finestra chiusa mentre la misurazione era in corso

    # ------------------------------------------------------------- Meteo/News

    def _refresh_weather(self):
        threading.Thread(target=self._fetch_weather, daemon=True).start()
        self.after(15 * 60 * 1000, self._refresh_weather)

    def _fetch_weather(self):
        data = get_weather()

        def apply():
            if "error" in data:
                self.weather_icon_label.configure(text="⚠️")
                self.weather_temp_label.configure(text="--°C")
                self.weather_cond_label.configure(text="Meteo non disponibile")
                return

            self.weather_city_label.configure(text=data["city"])
            self.weather_icon_label.configure(text=data["icon"])
            self.weather_temp_label.configure(text=f"{data['temp']:.0f}°C")
            self.weather_cond_label.configure(text=f"{data['condition']} · vento {data['wind']:.0f} km/h")

            forecast = data.get("forecast", [])
            for i, (day_lbl, icon_lbl, temp_lbl) in enumerate(self.forecast_rows):
                if i < len(forecast):
                    day = forecast[i]
                    day_lbl.configure(text=day["day"])
                    icon_lbl.configure(text=day["icon"])
                    temp_lbl.configure(text=f"{day['temp_max']:.0f}° / {day['temp_min']:.0f}°")
                else:
                    day_lbl.configure(text="--")
                    icon_lbl.configure(text="")
                    temp_lbl.configure(text="--° / --°")

        try:
            self.after(0, apply)
        except RuntimeError:
            pass

    def _refresh_news(self):
        threading.Thread(target=self._fetch_news, daemon=True).start()
        self.after(10 * 60 * 1000, self._refresh_news)

    def _fetch_news(self):
        titles = get_news()

        def apply():
            self.news_box.configure(state="normal")
            self.news_box.delete("1.0", "end")
            for t in titles:
                self.news_box.insert("end", f"▸ {t}\n\n")
            self.news_box.configure(state="disabled")

        try:
            self.after(0, apply)
        except RuntimeError:
            pass

    def _load_initial_usage(self):
        """Mostra subito nel footer il consumo di oggi letto da disco, senza
        aspettare che il core (in un altro thread) mandi il primo messaggio."""
        try:
            with open("config/usage.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == datetime.now().date().isoformat():
                self._update_usage_label(data)
        except Exception:
            pass

    # ------------------------------------------------------------- Note

    def open_notes(self):
        win = ctk.CTkToplevel(self)
        win.title("Note")
        win.geometry("420x480")
        win.configure(fg_color=BG_PANEL)

        section_label(win, "LE MIE NOTE", color=MAGENTA).pack(pady=(16, 8), padx=16, anchor="w")

        textbox = ctk.CTkTextbox(win, font=FONT_MAIN, fg_color=BG_INPUT, text_color=TXT_BRIGHT, wrap="word")
        textbox.pack(fill="both", expand=True, padx=16, pady=8)
        textbox.insert("1.0", self._load_notes())

        def save_and_close():
            self._save_notes(textbox.get("1.0", "end-1c"))
            win.destroy()

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))
        ctk.CTkButton(btn_frame, text="Salva", font=FONT_MAIN, fg_color=MAGENTA, text_color="#1a0410",
                      hover_color="#FF6FA8", command=save_and_close).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Chiudi senza salvare", font=FONT_SMALL, fg_color=BG_PANEL_ALT,
                      text_color=TXT_MAIN, hover_color="#1a2129", command=win.destroy).pack(side="left", padx=6)

    @staticmethod
    def _load_notes():
        if not os.path.exists(NOTES_FILE):
            return ""
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("content", "")
        except Exception:
            return ""

    @staticmethod
    def _save_notes(content):
        os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump({"content": content}, f, ensure_ascii=False, indent=2)