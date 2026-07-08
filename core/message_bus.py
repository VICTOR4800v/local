import queue

class MessageBus:
    def __init__(self):
        # Coda per i testi in arrivo (es. dal Discord Bot all'IA)
        self.input_queue = queue.Queue()
        # Coda per i comandi per la GUI (es. "mostra testo", "cambia stato")
        self.gui_queue = queue.Queue()
        # Coda per le risposte da far leggere al TTS
        self.tts_queue = queue.Queue()