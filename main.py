import argparse

from telegram.ext import Updater

from config import Config
from scheduler import TaskScheduler
import bot


def main():
    parser = argparse.ArgumentParser(description="Scheduled Task Bot")
    parser.add_argument("--token", required=True, help="Telegram bot token")
    parser.add_argument("--chat-id", required=True, help="Telegram chat ID")
    args = parser.parse_args()

    config = Config()

    updater = Updater(args.token, use_context=True)

    task_scheduler = TaskScheduler(updater.bot, args.chat_id, config)
    bot.init(config, task_scheduler)
    bot.register_handlers(updater.dispatcher)

    task_scheduler.start()

    print("Bot started")
    updater.start_polling()
    updater.idle()

    task_scheduler.stop()
    print("Bot stopped")


if __name__ == "__main__":
    main()
