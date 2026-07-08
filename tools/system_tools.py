import os
import subprocess
import threading
import time
import psutil
import pygetwindow as gw
import pyautogui
import webbrowser
import ctypes

class SystemTools:
    # Alias per i nomi comuni con cui un utente chiede di aprire un'app:
    # 'start "" "nome"' su Windows risolve sia i nomi in PATH sia le voci
    # registrate in App Paths, ma solo se il nome combacia con l'eseguibile
    # reale (es. "chrome.exe", non "Google Chrome"). Questa mappa traduce
    # i nomi parlati/italiani nell'eseguibile giusto.
    APP_ALIASES = {
        "chrome": "chrome", "google chrome": "chrome", "browser": "chrome",
        "edge": "msedge", "microsoft edge": "msedge",
        "firefox": "firefox",
        "word": "winword", "microsoft word": "winword",
        "excel": "excel", "microsoft excel": "excel",
        "powerpoint": "powerpnt",
        "blocco note": "notepad", "notepad": "notepad",
        "calcolatrice": "calc", "calculator": "calc",
        "paint": "mspaint",
        "esplora file": "explorer", "explorer": "explorer", "file explorer": "explorer",
        "spotify": "spotify",
        "vscode": "code", "visual studio code": "code",
        "telegram": "telegram",
        "discord": "discord",
        "steam": "steam",
        "gestione attività": "taskmgr", "task manager": "taskmgr",
        "cmd": "cmd", "prompt dei comandi": "cmd", "terminale": "cmd",
        "powershell": "powershell",
        "whatsapp": "whatsapp",
        "outlook": "outlook",
    }

    @staticmethod
    def open_web(url):
        webbrowser.open(url)
        return f"Aperto {url} nel browser."

    @staticmethod
    def launch_app(app_name):
        key = app_name.strip().lower()
        resolved = SystemTools.APP_ALIASES.get(key, app_name)
        try:
            # Passa dalla shell di Windows (stesso meccanismo di Win+R):
            # risolve sia i comandi in PATH sia le voci App Paths del
            # registro (chrome, spotify, discord, ecc. anche se non sono
            # nel PATH), a differenza di subprocess.Popen(app_name) diretto.
            subprocess.Popen(f'start "" "{resolved}"', shell=True)
            return f"Applicazione {app_name} avviata."
        except Exception as e:
            return f"Errore nell'avvio di {app_name}: {str(e)}"

    @staticmethod
    def exit_app():
        """Chiude completamente JARVIS (processo e GUI inclusi)."""
        def _shutdown():
            # Piccolo ritardo per permettere alla risposta finale di essere
            # mostrata/pronunciata prima che il processo termini davvero.
            time.sleep(2.5)
            os._exit(0)
        threading.Thread(target=_shutdown, daemon=True).start()
        return "Spegnimento di JARVIS in corso. A presto."

    @staticmethod
    def exec_terminal(command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr

    @staticmethod
    def manage_file(action, path):
        if action == "create":
            open(path, 'w').close()
            return f"File creato: {path}"
        elif action == "delete":
            if os.path.exists(path): os.remove(path)
            return f"File eliminato: {path}"
        return "Azione non supportata"

    @staticmethod
    def write_file(path, content):
        """Scrive (sovrascrivendo) del testo dentro un file, creandolo se non esiste."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Contenuto scritto in {path}"
        except Exception as e:
            return f"Errore durante la scrittura del file {path}: {str(e)}"

    @staticmethod
    def read_file(path):
        """Legge e restituisce il contenuto testuale di un file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return content if content else "(il file è vuoto)"
        except Exception as e:
            return f"Errore durante la lettura del file {path}: {str(e)}"

    @staticmethod
    def control_volume(level):
        # Metodo semplice: preme i tasti volume per alzarlo/abbassarlo
        # level 1 = alza, level -1 = abbassa
        if level > 50:
            for _ in range(10): pyautogui.press('volumeup')
        else:
            for _ in range(10): pyautogui.press('volumedown')
        return "Volume regolato."

    @staticmethod
    def take_screenshot():
        pyautogui.screenshot("screenshot_jarvis.png")
        return "Screenshot salvato come screenshot_jarvis.png"

    @staticmethod
    def kill_process(pid):
        try:
            psutil.Process(pid).terminate()
            return f"Processo {pid} terminato."
        except Exception as e:
            return f"Errore: {str(e)}"

    @staticmethod
    def get_cpu_usage():
        return f"Uso CPU: {psutil.cpu_percent(interval=1)}%"

    @staticmethod
    def get_ram_usage():
        return f"Uso RAM: {psutil.virtual_memory().percent}%"

    @staticmethod
    def get_disk_space():
        disk = psutil.disk_usage('C:\\')
        return f"Spazio libero su C: {disk.free / (1024**3):.2f} GB"

    @staticmethod
    def read_clipboard():
        return pyautogui.paste()

    @staticmethod
    def write_clipboard(text):
        pyautogui.copy(text)
        return "Testo copiato negli appunti."

    @staticmethod
    def minimize_window(title):
        windows = gw.getWindowsWithTitle(title)
        if windows:
            windows[0].minimize()
            return f"Finestra {title} minimizzata."
        return "Finestra non trovata"

    @staticmethod
    def maximize_window(title):
        windows = gw.getWindowsWithTitle(title)
        if windows:
            windows[0].maximize()
            return f"Finestra {title} massimizzata."
        return "Finestra non trovata"

    @staticmethod
    def get_active_window():
        return gw.getActiveWindow().title

    @staticmethod
    def shutdown_system(delay):
        os.system(f"shutdown /s /t {delay}")
        return f"Sistema in spegnimento tra {delay} secondi."