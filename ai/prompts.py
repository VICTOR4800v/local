SYSTEM_PROMPT = """
Sei JARVIS, un assistente IA desktop avanzato. Rispondi in modo conciso e diretto.
Hai accesso a un ampio set di strumenti per controllare il PC dell'utente, monitorare
GitHub/Calendar/Email, creare automazioni pianificate (Natural Language Cron) e
tenere traccia di abitudini quotidiane (Habit tracking).
Usa gli strumenti SOLO quando necessario per eseguire i comandi dell'utente.

Quando l'utente ti chiede di pianificare qualcosa (es. "ogni giorno alle 21 controlla
le mail e crea un report"), usa il tool 'create_schedule' passando l'orario e il
comando esatto da rieseguire in futuro: quel comando verrà rieseguito automaticamente
da te stesso quando il job scatta, quindi scrivilo come lo scriveresti a te stesso.

Quando l'utente vuole invece costruire un'abitudine ricorrente (es. "voglio bere
più acqua ogni giorno alle 15", "ricordami di allenarmi ogni lunedì mercoledì e
venerdì alle 18"), usa 'create_habit': a differenza di uno schedule, l'abitudine
manda solo un promemoria diretto all'orario indicato (non riesegue un comando IA
completo) e tiene traccia di uno streak di giorni consecutivi. Usa 'list_habits'
per elencarle, 'complete_habit' quando l'utente dice di aver fatto un'abitudine,
'delete_habit' per rimuoverla.

Se l'utente vuole scrivere del testo dentro un file (es. "scrivi 'appunto' dentro
note.txt", "puoi scriverci dentro?"), usa SEMPRE 'write_file' passando il
contenuto esatto: 'manage_file' crea solo file vuoti, non scrive testo al suo
interno. Usa 'read_file' se l'utente chiede di leggere cosa contiene un file.

Se l'utente ti chiede esplicitamente di chiuderti, spegnerti, uscire o terminare
il programma (es. "chiuditi", "esci", "spegniti", "chiudi il programma", "esci da
JARVIS"), usa il tool 'exit_app'. Non usarlo mai per richieste ambigue o non
esplicite: solo quando l'intento di chiudere il programma è chiaro.
"""

# Definizione dei Tools per il Function Calling di Groq
TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "open_web", "description": "Apre un URL nel browser", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "launch_app", "description": "Avvia un'applicazione Windows", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]}}},
    {"type": "function", "function": {"name": "exec_terminal", "description": "Esegue un comando cmd o PowerShell sicuro", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "manage_file", "description": "Crea o elimina un file (vuoto)", "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["create", "delete"]}, "path": {"type": "string"}}, "required": ["action", "path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Scrive (sovrascrivendo) del testo dentro un file, creandolo se non esiste. Usa questo tool ogni volta che l'utente chiede di scrivere/inserire contenuto dentro un file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Legge e restituisce il contenuto testuale di un file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_email", "description": "Cerca parole chiave nelle email", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "control_volume", "description": "Alza o abbassa il volume di Windows", "parameters": {"type": "object", "properties": {"level": {"type": "integer", "description": "Da 0 a 100"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "take_screenshot", "description": "Cattura lo schermo e salva l'immagine", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "kill_process", "description": "Termina un processo", "parameters": {"type": "object", "properties": {"pid": {"type": "integer"}}, "required": ["pid"]}}},
    {"type": "function", "function": {"name": "get_cpu_usage", "description": "Ottieni percentuale uso CPU", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_ram_usage", "description": "Ottieni percentuale uso RAM", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_disk_space", "description": "Ottieni spazio libero su disco", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_clipboard", "description": "Leggi il testo negli appunti", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "write_clipboard", "description": "Scrivi testo negli appunti", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "minimize_window", "description": "Minimizza una finestra tramite titolo", "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "maximize_window", "description": "Massimizza una finestra tramite titolo", "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "get_active_window", "description": "Ottieni il titolo della finestra attiva", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "shutdown_system", "description": "Spegne il PC", "parameters": {"type": "object", "properties": {"delay": {"type": "integer"}}, "required": ["delay"]}}},
    {"type": "function", "function": {"name": "write_excel", "description": "Scrivi dati in un file Excel", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "data": {"type": "array", "items": {"type": "string"}}}, "required": ["filepath", "data"]}}},

    # --- Sync tools reali (GitHub / Calendar) ---
    {"type": "function", "function": {"name": "get_github_activity", "description": "Controlla l'attività recente sui repository GitHub (commit, notifiche)", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_calendar_events", "description": "Controlla gli appuntamenti in agenda per oggi", "parameters": {"type": "object", "properties": {}}}},

    # --- Natural Language Cron (Scheduler) ---
    {"type": "function", "function": {"name": "create_schedule", "description": "Crea un'automazione pianificata che rieseguirà un comando all'orario indicato", "parameters": {"type": "object", "properties": {
        "hour": {"type": "integer", "description": "Ora del giorno, 0-23"},
        "minute": {"type": "integer", "description": "Minuto, 0-59 (default 0)"},
        "day_of_week": {"type": "string", "description": "Giorni della settimana, es. 'mon-fri' o '*' per tutti i giorni (default '*')"},
        "command": {"type": "string", "description": "Il comando esatto da rieseguire quando il job scatta"}
    }, "required": ["hour", "command"]}}},
    {"type": "function", "function": {"name": "list_schedules", "description": "Elenca tutte le automazioni pianificate attive", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "delete_schedule", "description": "Elimina un'automazione pianificata tramite il suo id", "parameters": {"type": "object", "properties": {"schedule_id": {"type": "string"}}, "required": ["schedule_id"]}}},

    # --- Habit tracking (abitudini quotidiane) ---
    {"type": "function", "function": {"name": "create_habit", "description": "Crea una nuova abitudine ricorrente con promemoria giornaliero/settimanale e streak", "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "Nome dell'abitudine, es. 'Bere acqua' o 'Allenamento'"},
        "hour": {"type": "integer", "description": "Ora del promemoria, 0-23 (default 9)"},
        "minute": {"type": "integer", "description": "Minuto, 0-59 (default 0)"},
        "day_of_week": {"type": "string", "description": "Giorni della settimana, es. 'mon-fri' o '*' per tutti i giorni (default '*')"}
    }, "required": ["name"]}}},
    {"type": "function", "function": {"name": "list_habits", "description": "Elenca tutte le abitudini attive con il relativo streak", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "complete_habit", "description": "Segna un'abitudine come completata oggi e aggiorna lo streak", "parameters": {"type": "object", "properties": {"habit_id": {"type": "string"}}, "required": ["habit_id"]}}},
    {"type": "function", "function": {"name": "delete_habit", "description": "Elimina un'abitudine tramite il suo id", "parameters": {"type": "object", "properties": {"habit_id": {"type": "string"}}, "required": ["habit_id"]}}},

    # --- Controllo del programma ---
    {"type": "function", "function": {"name": "exit_app", "description": "Chiude e spegne completamente l'assistente JARVIS (GUI inclusa). Usalo quando l'utente chiede esplicitamente di chiudere, spegnere, uscire o terminare il programma (es. 'chiuditi', 'esci', 'spegniti', 'chiudi il programma')", "parameters": {"type": "object", "properties": {}}}}
]