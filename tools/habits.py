import json
import os
import uuid
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

HABITS_FILE = "config/habits.json"


class HabitManager:
    """
    Gestisce le abitudini ricorrenti dell'utente (Habit tracking).

    A differenza di uno 'schedule' (che rieseguirà un comando IA completo),
    un'abitudine è più leggera: registra solo un promemoria vocale/testuale
    all'orario indicato ("è ora di fare X") e tiene traccia di uno streak
    (giorni consecutivi in cui l'utente l'ha segnata come completata).
    Usa un proprio BackgroundScheduler, indipendente da quello delle
    automazioni, per non mischiare le due responsabilità.
    """

    def __init__(self, bus):
        self.bus = bus
        self.scheduler = BackgroundScheduler()
        self.habits = self._load()

    def _load(self):
        if not os.path.exists(HABITS_FILE):
            return []
        try:
            with open(HABITS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self):
        os.makedirs(os.path.dirname(HABITS_FILE), exist_ok=True)
        with open(HABITS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.habits, f, indent=2, ensure_ascii=False)

    def _remind(self, habit_id):
        """Callback dello scheduler: manda un promemoria diretto (no IA, no costo API)."""
        habit = next((h for h in self.habits if h["id"] == habit_id), None)
        if not habit:
            return
        text = f"⏰ Promemoria abitudine: è ora di '{habit['name']}'."
        self.bus.gui_queue.put({"type": "text", "data": text})
        self.bus.tts_queue.put(text)

    def _register_job(self, habit):
        trigger = CronTrigger(
            hour=habit.get("hour", 9),
            minute=habit.get("minute", 0),
            day_of_week=habit.get("day_of_week", "*"),
        )
        self.scheduler.add_job(
            self._remind,
            trigger=trigger,
            args=[habit["id"]],
            id=f"habit_{habit['id']}",
            replace_existing=True,
        )

    def start(self):
        for h in self.habits:
            self._register_job(h)
        self.scheduler.start()
        print(f"[Habits] Avviato con {len(self.habits)} abitudini caricate.")

    # ---- Metodi esposti come tool all'IA (vedi ai/prompts.py e tools/manager.py) ----

    def create_habit(self, name, hour=9, minute=0, day_of_week="*"):
        """Crea una nuova abitudine con promemoria ricorrente."""
        habit = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "hour": hour,
            "minute": minute,
            "day_of_week": day_of_week,
            "streak": 0,
            "last_completed": None,
        }
        self.habits.append(habit)
        self._save()
        self._register_job(habit)
        return (
            f"Abitudine creata: '{name}', promemoria alle {hour:02d}:{minute:02d} "
            f"({day_of_week})."
        )

    def list_habits(self):
        """Elenca tutte le abitudini con lo streak attuale."""
        if not self.habits:
            return "Nessuna abitudine impostata al momento."
        lines = [
            f"- [{h['id']}] {h['name']} — promemoria {h['hour']:02d}:{h['minute']:02d} "
            f"({h['day_of_week']}), streak: {h['streak']} giorni"
            + (" (già fatta oggi)" if h["last_completed"] == date.today().isoformat() else "")
            for h in self.habits
        ]
        return "Abitudini attive:\n" + "\n".join(lines)

    def complete_habit(self, habit_id):
        """Segna un'abitudine come completata oggi e aggiorna lo streak."""
        habit = next((h for h in self.habits if h["id"] == habit_id), None)
        if not habit:
            return f"Nessuna abitudine trovata con id '{habit_id}'."
        today = date.today().isoformat()
        if habit["last_completed"] == today:
            return f"'{habit['name']}' è già stata segnata come completata oggi."
        habit["streak"] += 1
        habit["last_completed"] = today
        self._save()
        return f"'{habit['name']}' completata! Streak attuale: {habit['streak']} giorni."

    def delete_habit(self, habit_id):
        """Elimina un'abitudine tramite il suo id."""
        before = len(self.habits)
        self.habits = [h for h in self.habits if h["id"] != habit_id]
        if len(self.habits) == before:
            return f"Nessuna abitudine trovata con id '{habit_id}'."
        self._save()
        try:
            self.scheduler.remove_job(f"habit_{habit_id}")
        except Exception:
            pass
        return f"Abitudine '{habit_id}' eliminata."