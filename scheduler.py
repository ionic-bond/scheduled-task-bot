import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import llm


class TaskScheduler:
    def __init__(self, bot, chat_id, config):
        self.scheduler = BackgroundScheduler()
        self.bot = bot
        self.chat_id = chat_id
        self.config = config

    def start(self):
        self.scheduler.start()
        self.reload_tasks()
        print("Scheduler started")

    def stop(self):
        self.scheduler.shutdown()

    def reload_tasks(self):
        self.scheduler.remove_all_jobs()
        for task in self.config.data["tasks"]:
            self._add_job(task)

    def _add_job(self, task):
        try:
            trigger = CronTrigger.from_crontab(task["cron"])
            self.scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=f"task_{task['id']}",
                args=[task["id"], False],
                replace_existing=True
            )
            print(f"Job scheduled for task #{task['id']}: {task['cron']}")
        except Exception as e:
            print(f"Failed to schedule task #{task['id']}: {e}")

    def add_task(self, task):
        self._add_job(task)

    def remove_task(self, task_id):
        try:
            self.scheduler.remove_job(f"task_{task_id}")
        except Exception:
            pass

    def run_task_now(self, task_id):
        thread = threading.Thread(target=self._execute_task, args=(task_id, True), daemon=True)
        thread.start()

    def _execute_task(self, task_id, manual=False):
        task = self.config.get_task(task_id)
        if not task:
            print(f"Task #{task_id} not found, skipping")
            return

        retry_count = self.config.data.get("retry_count", 3)
        last_error = None

        for attempt in range(1, retry_count + 1):
            try:
                print(f"Executing task #{task_id}, attempt {attempt}/{retry_count}")
                response = llm.query(
                    self.config.data["base_url"],
                    self.config.data["api_key"],
                    self.config.data["model"],
                    task["instruction"]
                )
                print(f"Task #{task_id} response:\n{response}")

                if response.strip().startswith(llm.NO_UPDATE_TOKEN):
                    print(f"Task #{task_id}: No update")
                    if manual:
                        self.bot.send_message(
                            chat_id=self.chat_id,
                            text=f"ℹ️ Task #{task_id}: No valuable information found."
                        )
                else:
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"📋 Task #{task_id} Report\n\n{response}"
                    )
                return

            except Exception as e:
                last_error = e
                print(f"Task #{task_id} attempt {attempt} failed: {e}")
                if attempt < retry_count:
                    time.sleep(5)

        self.bot.send_message(
            chat_id=self.chat_id,
            text=f"❌ Task #{task_id} failed after {retry_count} attempts.\nLast error: {last_error}"
        )
