"""
Modalità VOCE LIVE (sperimentale): streaming audio bidirezionale nativo
tramite la Gemini Live API, ispirato all'architettura di Mark XLVIII
(https://github.com/FatihMakes/Mark-XLVIII, licenza CC BY-NC 4.0 — qui
il codice è riscritto da zero per il tuo ToolManager, non copiato).

Differenza rispetto al flusso normale (ai/llm.py + audio/tts.py):
 - qui NON c'è un giro discreto testo -> generate_content -> testo -> file
   mp3 -> pygame. Il microfono viene inviato in continuo a un modello Gemini
   "native audio" via WebSocket persistente (Live API), che risponde con
   audio grezzo mentre ancora ti ascolta: latenza molto più bassa.
 - i tool restano ESATTAMENTE gli stessi definiti in ai/prompts.py e
   eseguiti dal tuo ToolManager: solo il trasporto cambia.

Requisiti aggiuntivi: `pip install sounddevice` (serve PortAudio installato
sul sistema; su Windows di solito funziona senza passi extra).

ATTENZIONE:
 - Il nome del modello Live "native audio" è un preview e Google lo
   rinomina/aggiorna spesso: verifica il nome corrente su
   https://ai.google.dev/gemini-api/docs/live-guide prima di lanciare.
 - Questo modulo è volutamente più semplice della versione di Mark XLVIII:
   manca ad es. l'interrupt istantaneo "taglia a metà frase" e la gestione
   fine degli edge case di sessione. Funziona, ma è un punto di partenza,
   non una copia 1:1 di un sistema production-ready.
"""
import asyncio
import threading
import traceback

import sounddevice as sd
from google import genai
from google.genai import types

from ai.prompts import SYSTEM_PROMPT, TOOLS_SCHEMA

# Verifica il nome aggiornato su ai.google.dev prima dell'uso: i modelli
# "preview" di Google cambiano identificatore periodicamente.
LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

CHANNELS = 1
SEND_SAMPLE_RATE = 16000     # frequenza richiesta dalla Live API in ingresso
RECEIVE_SAMPLE_RATE = 24000  # frequenza dell'audio restituito dal modello
CHUNK_SIZE = 1024


def list_audio_devices():
    """
    Stampa tutti i device audio visti da PortAudio, con il loro indice.
    Utile quando lo stream fallisce con 'Error querying device -1' (nessun
    device di default valido): prendi l'indice del microfono/altoparlante
    che vuoi usare da qui e passalo a JarvisLiveVoice(input_device=...,
    output_device=...) oppure impostalo in config/settings.yaml
    (mic_device / speaker_device).
    """
    devices = sd.query_devices()
    lines = [f"[{i}] {d['name']}  (in:{d['max_input_channels']} out:{d['max_output_channels']})"
             for i, d in enumerate(devices)]
    print("\n".join(lines))
    print(f"Default device attuale (input, output): {sd.default.device}")
    return lines


def _to_gemini_tools(openai_style_schema):
    """Stessa conversione già presente in ai/llm.py: i tool restano identici."""
    declarations = []
    for entry in openai_style_schema:
        fn = entry["function"]
        declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {"type": "object", "properties": {}}),
            )
        )
    return [types.Tool(function_declarations=declarations)]


class JarvisLiveVoice:
    """
    Gira in un thread proprio con il suo event loop asyncio, separato dal
    loop principale in core/engine.py: le due modalità (testo/tool classica
    e voce live) non si toccano e non si bloccano a vicenda.
    """

    def __init__(self, api_key, tool_manager, bus, input_device=None, output_device=None):
        self.client = genai.Client(api_key=api_key)
        self.tool_manager = tool_manager
        self.bus = bus
        self.gemini_tools = _to_gemini_tools(TOOLS_SCHEMA)

        # Indice (int) o nome (str, anche parziale) del device da usare.
        # None = lascia decidere a PortAudio il device di default: se sul tuo
        # PC questo fallisce con "Error querying device -1", chiama
        # list_audio_devices() per trovare l'indice giusto e passalo qui.
        self.input_device = input_device
        self.output_device = output_device

        self.session = None
        self.audio_in_queue = None
        self.out_queue = None
        self._thread = None
        self.running = False
        self._is_speaking = False

    # ------------------------------------------------------------ ciclo

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _run_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except Exception as e:
            print(f"[LiveVoice] Errore fatale: {e}")
            traceback.print_exc()
            msg = f"Voce live interrotta per un errore: {e}"
            if "device" in str(e).lower():
                try:
                    lines = list_audio_devices()
                    msg += (
                        "\n\nElenco device audio rilevati (usa l'indice tra [ ] per "
                        "input_device/output_device in JarvisLiveVoice):\n" + "\n".join(lines)
                    )
                except Exception:
                    pass
            self.bus.gui_queue.put({"type": "text", "data": msg})
        finally:
            self.running = False
            self.bus.gui_queue.put({"type": "status", "data": "idle"})

    async def _main(self):
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=SYSTEM_PROMPT,
            tools=self.gemini_tools,
            output_audio_transcription={},
            input_audio_transcription={},
        )
        async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            self.session = session
            self.audio_in_queue = asyncio.Queue()
            self.out_queue = asyncio.Queue(maxsize=20)

            self.bus.gui_queue.put({"type": "status", "data": "listening"})

            tasks = [
                asyncio.create_task(self._send_realtime()),
                asyncio.create_task(self._listen_mic()),
                asyncio.create_task(self._receive()),
                asyncio.create_task(self._play()),
                asyncio.create_task(self._watch_stop()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                if not t.cancelled() and t.exception():
                    print(f"[LiveVoice] Task terminato con errore: {t.exception()}")

    async def _watch_stop(self):
        """Termina (e quindi fa terminare la sessione) quando self.stop() viene chiamato."""
        while self.running:
            await asyncio.sleep(0.2)

    # ------------------------------------------------------------- audio

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_mic(self):
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            # Non mandare il microfono mentre JARVIS sta parlando, altrimenti
            # rischia di "sentire" la propria voce dagli altoparlanti.
            if not self._is_speaking:
                # RawInputStream passa un buffer cffi, non un array numpy:
                # bytes(...) lo converte senza bisogno di numpy installato.
                data = bytes(indata)
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait, {"data": data, "mime_type": "audio/pcm"}
                )

        with sd.RawInputStream(
            samplerate=SEND_SAMPLE_RATE, channels=CHANNELS, dtype="int16",
            blocksize=CHUNK_SIZE, callback=callback, device=self.input_device,
        ):
            while True:
                await asyncio.sleep(0.1)

    async def _receive(self):
        async for response in self.session.receive():
            if response.data:
                self.audio_in_queue.put_nowait(response.data)

            if response.server_content and response.server_content.turn_complete:
                # Fine turno del modello: sblocca il microfono a breve.
                async def _release():
                    await asyncio.sleep(0.3)
                    self._is_speaking = False
                    self.bus.gui_queue.put({"type": "speaking", "data": False})
                asyncio.create_task(_release())

            if response.tool_call:
                fn_responses = []
                loop = asyncio.get_event_loop()
                for fc in response.tool_call.function_calls:
                    args = dict(fc.args or {})
                    print(f"[LiveVoice] Tool: {fc.name} {args}")
                    # Il tuo ToolManager.execute è sincrono: lo giro in un
                    # executor per non bloccare il loop asyncio.
                    result = await loop.run_in_executor(
                        None, self.tool_manager.execute, fc.name, args
                    )
                    fn_responses.append(
                        types.FunctionResponse(id=fc.id, name=fc.name, response={"result": str(result)})
                    )
                await self.session.send_tool_response(function_responses=fn_responses)

    async def _play(self):
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=CHUNK_SIZE,
            device=self.output_device,
        )
        stream.start()
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                if not self._is_speaking:
                    self._is_speaking = True
                    self.bus.gui_queue.put({"type": "speaking", "data": True})
                await asyncio.to_thread(stream.write, chunk)
        finally:
            stream.stop()
            stream.close()