import asyncio
import edge_tts
import os
import uuid
import pygame

class TTSEngine:
    def __init__(self):
        # Inizializza pygame solo per l'audio
        pygame.mixer.init()

    def speak(self, text):
        if not text:
            return

        # Nome file UNIVOCO per ogni chiamata: se due risposte arrivano vicine
        # (o il file precedente non è stato ancora rilasciato da Windows),
        # non ci sono più conflitti/PermissionError sullo stesso nome file.
        audio_file = f"jarvis_response_{uuid.uuid4().hex}.mp3"

        async def generate_audio():
            # Usa voce italiana di Microsoft
            communicate = edge_tts.Communicate(text, "it-IT-DiegoNeural")
            await communicate.save(audio_file)

        try:
            asyncio.run(generate_audio())

            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            # Attendi che la riproduzione finisca
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"[TTS] Errore durante la sintesi vocale: {e}")
        finally:
            # Rilascia esplicitamente il file prima di eliminarlo (necessario su Windows)
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            try:
                os.remove(audio_file)
            except Exception:
                pass