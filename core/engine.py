import asyncio
import threading
import queue
import yaml
import json
from datetime import datetime
from core.message_bus import MessageBus
from core.scheduler import JarvisScheduler
from ai.llm import JarvisAI
from audio.tts import TTSEngine
from tools.manager import ToolManager
from tools.habits import HabitManager
from tools.sync_tools import SyncTools
from gui.services import get_weather
from ai.live_voice import JarvisLiveVoice

class JarvisCore:
    def __init__(self):
        # Carica la configurazione
        with open("config/settings.yaml", "r") as f:
            self.config = yaml.safe_load(f)

        self.bus = MessageBus()
        self.tts = TTSEngine()

        # Scheduler (Natural Language Cron) - creato prima del ToolManager
        # perché i suoi metodi vengono esposti come tool all'IA
        self.scheduler = JarvisScheduler(self.bus)

        # Habit tracker - stesso discorso: creato prima del ToolManager
        # perché create_habit/list_habits/complete_habit/delete_habit
        # vengono esposti come tool all'IA
        self.habits = HabitManager(self.bus)

        self.tools = ToolManager(self.scheduler, self.habits)
        self.ai = JarvisAI(self.config['gemini_api_key'], self.tools)

        # Modalità VOCE LIVE (sperimentale, vedi ai/live_voice.py): stesso
        # ToolManager della modalità testuale, trasporto audio diverso.
        # mic_device/speaker_device in config/settings.yaml sono opzionali:
        # indice numerico del device PortAudio (vedi ai.live_voice.list_audio_devices()).
        # Se assenti, si usa il device di default del sistema.
        self.live_voice = JarvisLiveVoice(
            self.config['gemini_api_key'], self.tools, self.bus,
            input_device=self.config.get('mic_device'),
            output_device=self.config.get('speaker_device'),
        )

        self.running = True

    async def process_input(self):
        """Loop principale che ascolta la queue e processa i comandi (dalla GUI o dallo scheduler)."""
        while self.running:
            if not self.bus.input_queue.empty():
                user_text = self.bus.input_queue.get()

                # Comando speciale (mandato dal bottone in GUI, non digitato
                # dall'utente): accende/spegne la modalità voce live senza
                # passare dal loop testuale/tool normale.
                if user_text == "__TOGGLE_LIVE_VOICE__":
                    if self.live_voice.running:
                        self.live_voice.stop()
                        self.bus.gui_queue.put({"type": "text", "data": "Modalità voce live disattivata."})
                    else:
                        self.live_voice.start()
                        self.bus.gui_queue.put({"type": "text", "data": "Modalità voce live attivata: parla pure."})
                    await asyncio.sleep(0.1)
                    continue

                self.bus.gui_queue.put({"type": "status", "data": "thinking"})

                try:
                    response_text, tool_used = await self.ai.process_command(user_text)
                except Exception as e:
                    # Ultima rete di sicurezza: qualunque eccezione non gestita
                    # qui ucciderebbe silenziosamente questo loop (la coroutine
                    # esce, nessuno rimette più lo stato a "idle") e la GUI
                    # resterebbe bloccata su "thinking" per sempre. Non deve
                    # MAI succedere: logghiamo e rispondiamo comunque.
                    print(f"[Core] Errore imprevisto processando il comando: {e}")
                    response_text = "Ho avuto un problema interno imprevisto, riprova."
                    tool_used = False

                if response_text:
                    self.bus.gui_queue.put({"type": "text", "data": response_text})
                    # Accoda la risposta per la sintesi vocale invece di avviare
                    # un thread ad-hoc: un solo worker TTS parla le frasi in
                    # sequenza, evitando sovrapposizioni e conflitti sul file audio.
                    self.bus.tts_queue.put(response_text)

                # Aggiorna il monitor token/richieste in GUI (footer in basso
                # a destra) con il consumo cumulato della giornata.
                self.bus.gui_queue.put({"type": "usage", "data": self.ai.usage.snapshot()})

                self.bus.gui_queue.put({"type": "status", "data": "idle"})
            await asyncio.sleep(0.1)

    def run_tts_worker(self):
        """Worker dedicato: consuma la tts_queue e parla una frase alla volta."""
        while self.running:
            try:
                text = self.bus.tts_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            # Segnala alla GUI l'inizio/fine della sintesi vocale, cosi' la
            # sfera olografica puo' "reagire" mentre JARVIS parla davvero
            # (self.tts.speak e' bloccante finche' l'audio non e' finito).
            self.bus.gui_queue.put({"type": "speaking", "data": True})
            self.tts.speak(text)
            self.bus.gui_queue.put({"type": "speaking", "data": False})

    def run_process_input(self):
        """Esegue il loop di elaborazione comandi IA impostando un loop per questo thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.process_input())

    # ------------------------------------------------------------ Briefing

    def _build_briefing_text(self):
        """
        Compone il briefing di avvio SENZA passare dall'IA: meteo, agenda,
        GitHub, automazioni e abitudini attive. Essendo puro codice (nessuna
        chiamata a Gemini) è istantaneo, non consuma quota API e funziona
        anche se l'IA non è raggiungibile.
        """
        ora = datetime.now().hour
        if ora < 6:
            saluto = "Buonanotte"
        elif ora < 12:
            saluto = "Buongiorno"
        elif ora < 18:
            saluto = "Buon pomeriggio"
        else:
            saluto = "Buonasera"

        parts = [f"{saluto}. Sistema JARVIS online."]

        weather = get_weather()
        if "error" not in weather:
            parts.append(
                f"A {weather['city']} ci sono {weather['temp']:.0f} gradi, "
                f"{weather['condition'].lower()}."
            )

        parts.append(SyncTools.get_calendar_events())
        parts.append(SyncTools.get_github_activity())

        if self.scheduler.jobs_data:
            parts.append(f"Hai {len(self.scheduler.jobs_data)} automazioni pianificate attive.")

        if self.habits.habits:
            oggi = datetime.now().date().isoformat()
            da_fare = [h for h in self.habits.habits if h["last_completed"] != oggi]
            if da_fare:
                parts.append(f"Hai {len(da_fare)} abitudini ancora da completare oggi.")
            else:
                parts.append("Hai già completato tutte le abitudini di oggi.")

        return " ".join(parts)

    def _run_startup_briefing(self):
        """Gira in un thread separato: fa chiamate di rete (meteo) che non devono bloccare l'avvio."""
        try:
            briefing = self._build_briefing_text()
        except Exception as e:
            briefing = f"Sistema JARVIS online. (Briefing non disponibile: {e})"
        self.bus.gui_queue.put({"type": "text", "data": briefing})
        self.bus.tts_queue.put(briefing)
        # Mostra subito il monitor token in GUI con il valore già accumulato
        # oggi (letto da config/usage.json), senza aspettare il primo comando.
        self.bus.gui_queue.put({"type": "usage", "data": self.ai.usage.snapshot()})


    def start(self):
        """Avvia tutti i moduli."""
        print("Avvio JARVIS Core...")

        # 1. Avvia lo scheduler delle automazioni (Natural Language Cron)
        self.scheduler.start()

        # 1b. Avvia lo scheduler dei promemoria delle abitudini (Habit tracking)
        self.habits.start()

        # 2. Avvia il worker TTS dedicato in background
        tts_thread = threading.Thread(target=self.run_tts_worker, daemon=True)
        tts_thread.start()

        # 2b. Briefing di avvio (meteo, agenda, GitHub, automazioni, abitudini):
        # in un thread a parte perché fa chiamate di rete bloccanti.
        threading.Thread(target=self._run_startup_briefing, daemon=True).start()

        # 3. Avvia il processore dei comandi nel thread corrente
        self.run_process_input()