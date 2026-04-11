import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "",
    "model": "",
    "retry_count": 3,
    "next_task_id": 1,
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
            print(f"Config loaded from {CONFIG_FILE}")
        else:
            print("No config file found, using defaults")

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print("Config saved")

    def get_task(self, task_id):
        for task in self.data["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def add_task(self, instruction, cron):
        task = {
            "id": self.data["next_task_id"],
            "instruction": instruction,
            "cron": cron
        }
        self.data["tasks"].append(task)
        self.data["next_task_id"] += 1
        self.save()
        return task

    def remove_task(self, task_id):
        self.data["tasks"] = [t for t in self.data["tasks"] if t["id"] != task_id]
        self.save()

    def update_task(self, task_id, **kwargs):
        task = self.get_task(task_id)
        if task:
            task.update(kwargs)
            self.save()
        return task
