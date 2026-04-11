from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, Filters, CallbackContext
)
from cron_descriptor import get_description
from apscheduler.triggers.cron import CronTrigger

import llm

SET_BASE_URL, SET_API_KEY = range(2)
MODEL_CHOOSE, MODEL_INPUT = range(2, 4)
RETRY_INPUT = 4
TASK_INSTRUCTION, TASK_CRON = range(5, 7)
EDIT_FIELD, EDIT_VALUE = range(7, 9)

config = None
task_scheduler = None


def init(cfg, scheduler):
    global config, task_scheduler
    config = cfg
    task_scheduler = scheduler


def describe_cron(cron):
    try:
        return get_description(cron)
    except Exception:
        return cron


def _task_keyboard(prefix):
    tasks = config.data["tasks"]
    if not tasks:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            f"#{t['id']} {t['instruction'][:30]}",
            callback_data=f"{prefix}_{t['id']}"
        )] for t in tasks]
    )


# ---- simple commands ----

def cmd_start(update: Update, context: CallbackContext):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    update.message.reply_text(
        "👋 Welcome to Scheduled Task Bot!\n\n"
        f"🕐 Server time: {now}\n\n"
        "Commands:\n"
        "/settings - View current settings\n"
        "/setapi - Set API base URL and key\n"
        "/setmodel - Set LLM model\n"
        "/setretry - Set retry count\n"
        "/tasks - List all tasks\n"
        "/addtask - Add a new task\n"
        "/taskinfo <id> - View task details\n"
        "/edittask <id> - Edit a task\n"
        "/deltask <id> - Delete a task\n"
        "/runtask <id> - Run a task now\n"
        "/cancel - Cancel current operation"
    )


def cmd_settings(update: Update, context: CallbackContext):
    d = config.data
    api_key_display = f"{d['api_key'][:8]}..." if d["api_key"] else "Not set"
    update.message.reply_text(
        f"⚙️ Current Settings\n\n"
        f"Base URL: {d['base_url'] or 'Not set'}\n"
        f"API Key: {api_key_display}\n"
        f"Model: {d['model'] or 'Not set'}\n"
        f"Retry Count: {d['retry_count']}"
    )


def cmd_tasks(update: Update, context: CallbackContext):
    tasks = config.data["tasks"]
    if not tasks:
        update.message.reply_text("No tasks configured. Use /addtask to create one.")
        return
    lines = ["📋 Tasks\n"]
    for t in tasks:
        preview = t["instruction"][:50] + ("..." if len(t["instruction"]) > 50 else "")
        lines.append(f"#{t['id']} | {describe_cron(t['cron'])}\n   {preview}")
    update.message.reply_text("\n".join(lines))


def _show_taskinfo(chat_context, task_id):
    task = config.get_task(task_id)
    if not task:
        chat_context(f"❌ Task #{task_id} not found.")
        return
    chat_context(
        f"📋 Task #{task['id']}\n\n"
        f"Schedule: {describe_cron(task['cron'])} ({task['cron']})\n\n"
        f"Instruction:\n{task['instruction']}"
    )


def cmd_taskinfo(update: Update, context: CallbackContext):
    if not context.args:
        kb = _task_keyboard("ti")
        if not kb:
            update.message.reply_text("No tasks configured.")
            return
        update.message.reply_text("Select a task:", reply_markup=kb)
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Invalid task ID.")
        return
    _show_taskinfo(update.message.reply_text, task_id)


def cb_taskinfo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    task_id = int(query.data.removeprefix("ti_"))
    _show_taskinfo(query.edit_message_text, task_id)


def _confirm_delete(chat_context, task_id):
    if not config.get_task(task_id):
        chat_context(f"❌ Task #{task_id} not found.")
        return
    keyboard = [[
        InlineKeyboardButton("✅ Confirm", callback_data=f"del_confirm_{task_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")
    ]]
    chat_context(f"Delete task #{task_id}?", reply_markup=InlineKeyboardMarkup(keyboard))


def cmd_deltask(update: Update, context: CallbackContext):
    if not context.args:
        kb = _task_keyboard("ds")
        if not kb:
            update.message.reply_text("No tasks configured.")
            return
        update.message.reply_text("Select a task to delete:", reply_markup=kb)
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Invalid task ID.")
        return
    _confirm_delete(update.message.reply_text, task_id)


def cb_deltask_select(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    task_id = int(query.data.removeprefix("ds_"))
    _confirm_delete(query.edit_message_text, task_id)


def cb_deltask(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "del_cancel":
        query.edit_message_text("Cancelled.")
        return
    task_id = int(query.data.removeprefix("del_confirm_"))
    config.remove_task(task_id)
    task_scheduler.remove_task(task_id)
    query.edit_message_text(f"✅ Task #{task_id} deleted.")


def _run_task(chat_context, task_id):
    if not config.get_task(task_id):
        chat_context(f"❌ Task #{task_id} not found.")
        return
    if not all([config.data["base_url"], config.data["api_key"], config.data["model"]]):
        chat_context("❌ Please configure API settings first (/setapi, /setmodel).")
        return
    chat_context(f"🔄 Running task #{task_id}...")
    task_scheduler.run_task_now(task_id)


def cmd_runtask(update: Update, context: CallbackContext):
    if not context.args:
        kb = _task_keyboard("rt")
        if not kb:
            update.message.reply_text("No tasks configured.")
            return
        update.message.reply_text("Select a task to run:", reply_markup=kb)
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Invalid task ID.")
        return
    _run_task(update.message.reply_text, task_id)


def cb_runtask(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    task_id = int(query.data.removeprefix("rt_"))
    _run_task(query.edit_message_text, task_id)


# ---- setapi conversation ----

def setapi_start(update: Update, context: CallbackContext):
    update.message.reply_text("Enter the API base URL (e.g. https://api.example.com/v1):")
    return SET_BASE_URL


def setapi_base_url(update: Update, context: CallbackContext):
    config.data["base_url"] = update.message.text.strip()
    update.message.reply_text("Enter the API key:")
    return SET_API_KEY


def setapi_api_key(update: Update, context: CallbackContext):
    config.data["api_key"] = update.message.text.strip()
    config.save()
    update.message.reply_text("✅ API settings saved.")
    return ConversationHandler.END


# ---- setmodel conversation ----

def setmodel_start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("📋 List available models", callback_data="model_list")],
        [InlineKeyboardButton("✏️ Enter manually", callback_data="model_manual")]
    ]
    update.message.reply_text(
        "How would you like to set the model?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MODEL_CHOOSE


def setmodel_choose(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "model_list":
        if not config.data["base_url"] or not config.data["api_key"]:
            query.edit_message_text("❌ Please set API settings first (/setapi).")
            return ConversationHandler.END
        try:
            models = llm.list_models(config.data["base_url"], config.data["api_key"])
            if not models:
                query.edit_message_text("No models found. Enter model name manually:")
                return MODEL_INPUT
            context.user_data["model_list"] = models
            keyboard = [[InlineKeyboardButton(m, callback_data=f"m_{i}")] for i, m in enumerate(models)]
            query.edit_message_text(
                f"Select a model ({len(models)} available):",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return MODEL_INPUT
        except Exception as e:
            query.edit_message_text(f"❌ Failed to list models: {e}\n\nEnter model name manually:")
            return MODEL_INPUT
    else:
        query.edit_message_text("Enter the model name:")
        return MODEL_INPUT


def setmodel_input(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        query.answer()
        idx = int(query.data.removeprefix("m_"))
        model = context.user_data["model_list"][idx]
        query.edit_message_text(f"✅ Model set to: {model}")
    else:
        model = update.message.text.strip()
        update.message.reply_text(f"✅ Model set to: {model}")
    config.data["model"] = model
    config.save()
    return ConversationHandler.END


# ---- setretry conversation ----

def setretry_start(update: Update, context: CallbackContext):
    update.message.reply_text(
        f"Current retry count: {config.data['retry_count']}\nEnter new retry count:"
    )
    return RETRY_INPUT


def setretry_input(update: Update, context: CallbackContext):
    try:
        count = int(update.message.text.strip())
        if count < 1:
            raise ValueError
    except ValueError:
        update.message.reply_text("❌ Please enter a valid positive number.")
        return RETRY_INPUT
    config.data["retry_count"] = count
    config.save()
    update.message.reply_text(f"✅ Retry count set to: {count}")
    return ConversationHandler.END


# ---- addtask conversation ----

def addtask_start(update: Update, context: CallbackContext):
    update.message.reply_text("Enter the instruction for information retrieval:")
    return TASK_INSTRUCTION


def addtask_instruction(update: Update, context: CallbackContext):
    context.user_data["new_instruction"] = update.message.text.strip()
    update.message.reply_text(
        "Enter the cron schedule (e.g. '*/30 * * * *' for every 30 minutes):"
    )
    return TASK_CRON


def addtask_cron(update: Update, context: CallbackContext):
    cron = update.message.text.strip()
    try:
        CronTrigger.from_crontab(cron)
    except Exception:
        update.message.reply_text("❌ Invalid cron expression. Please try again:")
        return TASK_CRON

    task = config.add_task(context.user_data["new_instruction"], cron)
    task_scheduler.add_task(task)
    update.message.reply_text(f"✅ Task #{task['id']} created.\nSchedule: {describe_cron(cron)}")
    return ConversationHandler.END


# ---- edittask conversation ----

EDIT_SELECT = 9


def edittask_start(update: Update, context: CallbackContext):
    if not context.args:
        kb = _task_keyboard("es")
        if not kb:
            update.message.reply_text("No tasks configured.")
            return ConversationHandler.END
        update.message.reply_text("Select a task to edit:", reply_markup=kb)
        return EDIT_SELECT
    try:
        task_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ Invalid task ID.")
        return ConversationHandler.END
    return _edittask_show_fields(update.message.reply_text, context, task_id)


def edittask_select(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    task_id = int(query.data.removeprefix("es_"))
    return _edittask_show_fields(query.edit_message_text, context, task_id)


def _edittask_show_fields(chat_context, context, task_id):
    if not config.get_task(task_id):
        chat_context(f"❌ Task #{task_id} not found.")
        return ConversationHandler.END
    context.user_data["edit_task_id"] = task_id
    keyboard = [
        [InlineKeyboardButton("📝 Instruction", callback_data="edit_instruction")],
        [InlineKeyboardButton("⏰ Schedule", callback_data="edit_cron")]
    ]
    chat_context(
        f"Editing task #{task_id}. What would you like to change?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_FIELD


def edittask_field(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    field = query.data.removeprefix("edit_")
    context.user_data["edit_field"] = field
    task = config.get_task(context.user_data["edit_task_id"])
    current_value = task[field]
    if field == "instruction":
        query.edit_message_text(f"Current instruction:\n{current_value}\n\nEnter the new instruction:")
    else:
        query.edit_message_text(
            f"Current schedule: {describe_cron(current_value)} ({current_value})\n\n"
            f"Enter the new cron schedule:"
        )
    return EDIT_VALUE


def edittask_value(update: Update, context: CallbackContext):
    task_id = context.user_data["edit_task_id"]
    field = context.user_data["edit_field"]
    value = update.message.text.strip()

    if field == "cron":
        try:
            CronTrigger.from_crontab(value)
        except Exception:
            update.message.reply_text("❌ Invalid cron expression. Please try again:")
            return EDIT_VALUE

    config.update_task(task_id, **{field: value})
    task_scheduler.reload_tasks()
    update.message.reply_text(f"✅ Task #{task_id} updated.")
    return ConversationHandler.END


# ---- cancel ----

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# ---- handler registration ----

def register_handlers(dispatcher):
    dispatcher.add_handler(CommandHandler("start", cmd_start))
    dispatcher.add_handler(CommandHandler("help", cmd_start))
    dispatcher.add_handler(CommandHandler("settings", cmd_settings))
    dispatcher.add_handler(CommandHandler("tasks", cmd_tasks))
    dispatcher.add_handler(CommandHandler("taskinfo", cmd_taskinfo))
    dispatcher.add_handler(CommandHandler("deltask", cmd_deltask))
    dispatcher.add_handler(CommandHandler("runtask", cmd_runtask))
    dispatcher.add_handler(CallbackQueryHandler(cb_taskinfo, pattern=r"^ti_"))
    dispatcher.add_handler(CallbackQueryHandler(cb_deltask_select, pattern=r"^ds_"))
    dispatcher.add_handler(CallbackQueryHandler(cb_deltask, pattern=r"^del_"))
    dispatcher.add_handler(CallbackQueryHandler(cb_runtask, pattern=r"^rt_"))

    text_filter = Filters.text & ~Filters.command

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setapi", setapi_start)],
        states={
            SET_BASE_URL: [MessageHandler(text_filter, setapi_base_url)],
            SET_API_KEY: [MessageHandler(text_filter, setapi_api_key)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    ))

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setmodel", setmodel_start)],
        states={
            MODEL_CHOOSE: [CallbackQueryHandler(setmodel_choose, pattern=r"^model_")],
            MODEL_INPUT: [
                CallbackQueryHandler(setmodel_input, pattern=r"^m_"),
                MessageHandler(text_filter, setmodel_input),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    ))

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setretry", setretry_start)],
        states={
            RETRY_INPUT: [MessageHandler(text_filter, setretry_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    ))

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addtask", addtask_start)],
        states={
            TASK_INSTRUCTION: [MessageHandler(text_filter, addtask_instruction)],
            TASK_CRON: [MessageHandler(text_filter, addtask_cron)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    ))

    dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler("edittask", edittask_start)],
        states={
            EDIT_SELECT: [CallbackQueryHandler(edittask_select, pattern=r"^es_")],
            EDIT_FIELD: [CallbackQueryHandler(edittask_field, pattern=r"^edit_")],
            EDIT_VALUE: [MessageHandler(text_filter, edittask_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    ))
