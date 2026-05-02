import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Get bot token from environment variable
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables!")

# Simple in-memory storage (reminders will reset on restart)
reminders = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
🤖 *CodexProyBot - Reminder Bot* 🤖

Commands:
• `/remind [time] [task]` - Set a reminder
  Examples: `/remind 1m Test`, `/remind 2h Meeting`, `/remind 1d Pay bills`
• `/list` - View all reminders
• `/done [id]` - Mark task as done
• `/cancelall` - Cancel all reminders

Time formats: `30m` (minutes), `2h` (hours), `1d` (days)
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/remind 30m Buy groceries`", parse_mode='Markdown')
        return
    
    time_str = context.args[0]
    task = ' '.join(context.args[1:])
    
    # Parse time
    now = datetime.now(pytz.UTC)
    if time_str.endswith('m'):
        delta = timedelta(minutes=int(time_str[:-1]))
    elif time_str.endswith('h'):
        delta = timedelta(hours=int(time_str[:-1]))
    elif time_str.endswith('d'):
        delta = timedelta(days=int(time_str[:-1]))
    else:
        await update.message.reply_text("Invalid time format! Use: `30m`, `2h`, or `1d`", parse_mode='Markdown')
        return
    
    reminder_time = now + delta
    reminder_id = f"{chat_id}_{int(datetime.now().timestamp())}"
    
    if chat_id not in reminders:
        reminders[chat_id] = {}
    
    reminders[chat_id][reminder_id] = {'task': task, 'time': reminder_time.isoformat()}
    
    # Schedule reminder
    delay = (reminder_time - now).total_seconds()
    asyncio.create_task(send_reminder_after_delay(chat_id, reminder_id, task, delay))
    
    await update.message.reply_text(f"✅ Reminder set for {task} at {reminder_time.strftime('%H:%M UTC')}\nID: `{reminder_id}`", parse_mode='Markdown')

async def send_reminder_after_delay(chat_id, reminder_id, task, delay):
    await asyncio.sleep(delay)
    try:
        # Check if reminder still exists
        if chat_id in reminders and reminder_id in reminders[chat_id]:
            await application_instance.bot.send_message(
                chat_id=chat_id,
                text=f"⏰ **REMINDER:** {task}\n\nReply with `/done {reminder_id}` when complete!",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Reminder failed: {e}")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in reminders or not reminders[chat_id]:
        await update.message.reply_text("📭 No active reminders!")
        return
    
    message = "*Your reminders:*\n\n"
    for rid, r in reminders[chat_id].items():
        time_obj = datetime.fromisoformat(r['time'])
        message += f"🆔 `{rid}`\n📝 {r['task']}\n⏰ {time_obj.strftime('%H:%M UTC')}\n➖➖➖\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def done_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text("Please provide the reminder ID: `/done reminder_id`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    
    if chat_id in reminders and reminder_id in reminders[chat_id]:
        task = reminders[chat_id][reminder_id]['task']
        del reminders[chat_id][reminder_id]
        await update.message.reply_text(f"✅ Great job! Completed: {task}")
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id in reminders:
        reminders[chat_id] = {}
        await update.message.reply_text("✅ All reminders cancelled!")
    else:
        await update.message.reply_text("📭 No active reminders!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Global application instance
application_instance = None

async def main():
    global application_instance
    application_instance = Application.builder().token(TOKEN).build()
    
    application_instance.add_handler(CommandHandler("start", start))
    application_instance.add_handler(CommandHandler("remind", set_reminder))
    application_instance.add_handler(CommandHandler("list", list_reminders))
    application_instance.add_handler(CommandHandler("done", done_reminder))
    application_instance.add_handler(CommandHandler("cancelall", cancel_all))
    application_instance.add_error_handler(error_handler)
    
    print("Bot is starting...")
    await application_instance.initialize()
    await application_instance.start()
    await application_instance.updater.start_polling()
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await application_instance.updater.stop()
        await application_instance.stop()

if __name__ == '__main__':
    asyncio.run(main())
