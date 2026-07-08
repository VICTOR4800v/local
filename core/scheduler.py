import json
import os
import uuid
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

SCHEDULES_FILE = "config/schedules.json"


class JarvisScheduler:
    """
    Gestisce le automazioni pianificate (Natural Language Cron).

    L'IA traduce una frase dell'utente (es. "ogni giorno alle 21 controlla
    le mail e crea un report Excel") in una chiamata al tool 'create_schedule'.
    Quando il job scatta, il comando testuale originale viene reiniettato
    nella input_queue del MessageBus, esattamente come se l'utente lo avesse
    scritto/detto in quel momento: la pipeline IA + tools normale se ne occupa.
    """

    def __init__(self, bus):
        self.bus = bus
        self.scheduler = BackgroundScheduler()
        self.jobs_data = self._load_schedules()

    def _load_schedules(self):
        if not os.path.exists(SCHEDULES_FILE):
            return []
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_schedules(self):
        os.makedirs(os.path.dirname(SCHEDULES_FILE), exist_ok=True)
        with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
            json.dump(self.jobs_data, f, indent=2, ensure_ascii=False)

    def _trigger_command(self, command):
        """Callback eseguita dallo scheduler quando un job scatta."""
        self.bus.gui_queue.put({"type": "text", "data": f"[Automazione] Eseguo: {command}"})
        self.bus.input_queue.put(command)

    def _register_job(self, job):
        trigger = CronTrigger(
            hour=job.get("hour", "*"),
            minute=job.get("minute", 0),
            day_of_week=job.get("day_of_week", "*"),
        )
        self.scheduler.add_job(
            self._trigger_command,
            trigger=trigger,
            args=[job["command"]],
            id=job["id"],
            replace_existing=True,
        )

    def start(self):
        """Avvia lo scheduler e registra tutte le automazioni salvate su disco."""
        for job in self.jobs_data:
            self._register_job(job)
        self.scheduler.start()
        print(f"[Scheduler] Avviato con {len(self.jobs_data)} automazioni caricate.")

    # ---- Metodi esposti come tool all'IA (vedi ai/prompts.py e tools/manager.py) ----

    def create_schedule(self, hour, command, minute=0, day_of_week="*"):
        """Crea e salva una nuova automazione pianificata."""
        job = {
            "id": str(uuid.uuid4())[:8],
            "hour": hour,
            "minute": minute,
            "day_of_week": day_of_week,
            "command": command,
        }
        self.jobs_data.append(job)
        self._save_schedules()
        self._register_job(job)
        return f"Automazione creata: alle {hour:02d}:{minute:02d} ({day_of_week}) eseguirò '{command}'."

    def list_schedules(self):
        """Elenca tutte le automazioni attive."""
        if not self.jobs_data:
            return "Nessuna automazione pianificata al momento."
        lines = [
            f"- [{j['id']}] {j['hour']:02d}:{j['minute']:02d} ({j['day_of_week']}): {j['command']}"
            for j in self.jobs_data
        ]
        return "Automazioni attive:\n" + "\n".join(lines)

    def delete_schedule(self, schedule_id):
        """Elimina un'automazione tramite il suo id."""
        before = len(self.jobs_data)
        self.jobs_data = [j for j in self.jobs_data if j["id"] != schedule_id]
        if len(self.jobs_data) == before:
            return f"Nessuna automazione trovata con id '{schedule_id}'."
        self._save_schedules()
        try:
            self.scheduler.remove_job(schedule_id)
        except Exception:
            pass
        return f"Automazione '{schedule_id}' eliminata."