import threading
import customtkinter as ctk
print("CustomTkinter funziona perfettamente!")
from core.engine import JarvisCore
from gui.app import JarvisGUI
def main():
    # 1. Inizializza il Core di JARVIS
    jarvis_core = JarvisCore()
    
    
    # 2. Avvia il Core Engine in un thread separato (per non bloccare la GUI)
    core_thread = threading.Thread(target=jarvis_core.start, daemon=True)
    core_thread.start()
    
    # 3. Avvia la GUI nel thread principale (Tkinter lo richiede)
    app = JarvisGUI(jarvis_core.bus)
    app.mainloop()

if __name__ == "__main__":
    main()