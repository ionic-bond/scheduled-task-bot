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

    def _job_id(self, task):
        return f"task_{task['created_at']}"

    def _add_job(self, task):
        task_id = self.config.task_index(task)
        try:
            trigger = CronTrigger.from_crontab(task["cron"])
            self.scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=self._job_id(task),
                args=[task["created_at"], False],
                replace_existing=True
            )
            print(f"Job scheduled for task #{task_id}: {task['cron']}")
        except Exception as e:
            print(f"Failed to schedule task #{task_id}: {e}")

    def add_task(self, task):
        self._add_job(task)

    def remove_task(self, task):
        try:
            self.scheduler.remove_job(self._job_id(task))
        except Exception:
            pass

    def run_task_now(self, task):
        thread = threading.Thread(target=self._execute_task, args=(task["created_at"], True), daemon=True)
        thread.start()

    def _find_task_by_created_at(self, created_at):
        for task in self.config.data["tasks"]:
            if task["created_at"] == created_at:
                return task
        return None

    def _execute_task(self, created_at, manual=False):
        task = self._find_task_by_created_at(created_at)
        if not task:
            print(f"Task with created_at={created_at} not found, skipping")
            return

        task_id = self.config.task_index(task)
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
