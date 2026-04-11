import json
import os
from datetime import datetime

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "",
    "model": "",
    "retry_count": 3,
    "tasks": []
}


class Config:
    def __init__(self):
        self.data = DEFAULT_CONFIG.copy()
        self.data["tasks"] = []
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                self.data.update(saved)
            self._sort_tasks()
            print(f"Config loaded from {CONFIG_FILE}")
        else:
            print("No config file found, using defaults")

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print("Config saved")

    def _sort_tasks(self):
        self.data["tasks"].sort(key=lambda t: t["created_at"])

    def get_task(self, task_id):
        tasks = self.data["tasks"]
        if 1 <= task_id <= len(tasks):
            return tasks[task_id - 1]
        return None

    def add_task(self, instruction, cron):
        task = {
            "instruction": instruction,
            "cron": cron,
            "created_at": datetime.now().isoformat()
        }
        self.data["tasks"].append(task)
        self._sort_tasks()
        self.save()
        return task

    def remove_task(self, task_id):
        task = self.get_task(task_id)
        if task:
            self.data["tasks"].remove(task)
            self.save()

    def update_task(self, task_id, **kwargs):
        task = self.get_task(task_id)
        if task:
            task.update(kwargs)
            self.save()
        return task

    def task_index(self, task):
        try:
            return self.data["tasks"].index(task) + 1
        except ValueError:
            return None
