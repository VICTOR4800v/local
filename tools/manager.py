from tools.system_tools import SystemTools
from tools.sync_tools import SyncTools


class ToolManager:
    def __init__(self, scheduler=None, habit_manager=None):
        """
        scheduler: istanza di core.scheduler.JarvisScheduler.
        Passata da JarvisCore per esporre create_schedule/list_schedules/
        delete_schedule come tool richiamabili dall'IA.

        habit_manager: istanza di tools.habits.HabitManager.
        Passata da JarvisCore per esporre create_habit/list_habits/
        complete_habit/delete_habit come tool richiamabili dall'IA.
        """
        self.scheduler = scheduler
        self.habit_manager = habit_manager

        # Mappa i nomi dei tools (che l'IA legge in prompts.py) alle funzioni reali
        self.tools_map = {
            # System Tools
            "open_web": SystemTools.open_web,
            "launch_app": SystemTools.launch_app,
            "exec_terminal": SystemTools.exec_terminal,
            "manage_file": SystemTools.manage_file,
            "write_file": SystemTools.write_file,
            "read_file": SystemTools.read_file,
            "control_volume": SystemTools.control_volume,
            "take_screenshot": SystemTools.take_screenshot,
            "kill_process": SystemTools.kill_process,
            "get_cpu_usage": SystemTools.get_cpu_usage,
            "get_ram_usage": SystemTools.get_ram_usage,
            "get_disk_space": SystemTools.get_disk_space,
            "read_clipboard": SystemTools.read_clipboard,
            "write_clipboard": SystemTools.write_clipboard,
            "minimize_window": SystemTools.minimize_window,
            "maximize_window": SystemTools.maximize_window,
            "get_active_window": SystemTools.get_active_window,
            "shutdown_system": SystemTools.shutdown_system,
            "exit_app": SystemTools.exit_app,
            # Sync Tools
            "search_email": SyncTools.search_email,
            "write_excel": SyncTools.write_excel,
            "get_github_activity": SyncTools.get_github_activity,
            "get_calendar_events": SyncTools.get_calendar_events,
        }

        # Tool dello Scheduler (Natural Language Cron) - solo se lo scheduler è stato passato
        if self.scheduler is not None:
            self.tools_map.update({
                "create_schedule": self.scheduler.create_schedule,
                "list_schedules": self.scheduler.list_schedules,
                "delete_schedule": self.scheduler.delete_schedule,
            })

        # Tool delle Habit (abitudini) - solo se l'habit manager è stato passato
        if self.habit_manager is not None:
            self.tools_map.update({
                "create_habit": self.habit_manager.create_habit,
                "list_habits": self.habit_manager.list_habits,
                "complete_habit": self.habit_manager.complete_habit,
                "delete_habit": self.habit_manager.delete_habit,
            })

    def execute(self, tool_name, args):
        """Esegue il tool richiesto dall'IA passando gli argomenti."""
        if tool_name in self.tools_map:
            try:
                func = self.tools_map[tool_name]
                return func(**args)  # type: ignore
            except Exception as e:
                return f"Errore durante l'esecuzione del tool {tool_name}: {str(e)}"
        return f"Tool '{tool_name}' non riconosciuto."