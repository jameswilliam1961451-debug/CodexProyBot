import os
import logging
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token - REPLACE WITH YOUR ACTUAL TOKEN
TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Replace with your @CodexProyBot token

# Store reminders
reminders_file = 'reminders.json'
scheduler = BackgroundScheduler(timezone=pytz.UTC)

def load_reminders():
    try:
        with open(reminders_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_reminders(reminders):
    with open(reminders_file, 'w') as f:
        json.dump(reminders, f, indent=2)

reminders = load_reminders()

async def send_reminder(chat_id, reminder_id, task):
    keyboard = [[InlineKeyboardButton("✅ Mark as Done", callback_data=f"done_{reminder_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await application.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ REMINDER: {task}\n\nClick 'Mark as Done' when you complete this task.",
        reply_markup=reply_markup
    )

def schedule_reminder(chat_id, reminder_id, task, reminder_time):
    trigger = DateTrigger(run_date=reminder_time, timezone=pytz.UTC)
    scheduler.add_job(
        send_reminder,
        trigger,
        args=[chat_id, reminder_id, task],
        id=reminder_id,
        replace_existing=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
🤖 *Welcome to CodexProyBot - Reminder Bot!* 🤖

I help you remember your tasks:

Commands:
• `/remind [time] [task]` - Set a reminder
  Examples:
  - `/remind 30m Call mom`
  - `/remind 2h Complete report`
  - `/remind 1d Pay bills`

• `/list` - View all your reminders
• `/cancel [id]` - Cancel a reminder
• `/done [id]` - Mark task as done
• `/cancelall` - Cancel all reminders
• `/help` - Show this help

Time formats: `30m` (minutes), `2h` (hours), `1d` (days)
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text(
            "Please specify time and task!\n\nExample: `/remind 30m Buy groceries`",
            parse_mode='Markdown'
        )
        return
    
    time_str = context.args[0]
    task = ' '.join(context.args[1:])
    
    if not task:
        await update.message.reply_text("Please specify what you want to be reminded about!")
        return
    
    reminder_time = parse_time(time_str)
    
    if not reminder_time:
        await update.message.reply_text(
            "Invalid time format! Use:\n"
            "• `30m` for minutes\n"
            "• `2h` for hours\n"
            "• `1d` for days",
            parse_mode='Markdown'
        )
        return
    
    reminder_id = f"{chat_id}_{datetime.now().timestamp()}"
    
    if chat_id not in reminders:
        reminders[chat_id] = {}
    
    reminders[chat_id][reminder_id] = {
        'task': task,
        'time': reminder_time.isoformat(),
        'created_at': datetime.now(pytz.UTC).isoformat()
    }
    
    save_reminders(reminders)
    schedule_reminder(chat_id, reminder_id, task, reminder_time)
    
    time_display = reminder_time.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    await update.message.reply_text(
        f"✅ Reminder set!\n\n"
        f"📝 Task: {task}\n"
        f"⏰ Time: {time_display}\n"
        f"🆔 ID: `{reminder_id}`\n\n"
        f"I'll remind you then!",
        parse_mode='Markdown'
    )

def parse_time(time_str):
    now = datetime.now(pytz.UTC)
    
    if time_str.endswith('m'):
        try:
            minutes = int(time_str[:-1])
            return now + timedelta(minutes=minutes)
        except ValueError:
            return None
    elif time_str.endswith('h'):
        try:
            hours = int(time_str[:-1])
            return now + timedelta(hours=hours)
        except ValueError:
            return None
    elif time_str.endswith('d'):
        try:
            days = int(time_str[:-1])
            return now + timedelta(days=days)
        except ValueError:
            return None
    return None

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in reminders or not reminders[chat_id]:
        await update.message.reply_text("📭 You have no active reminders!")
        return
    
    message = "📋 *Your Active Reminders:*\n\n"
    for reminder_id, reminder in reminders[chat_id].items():
        time_obj = datetime.fromisoformat(reminder['time'])
        time_display = time_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
        message += f"🆔 `{reminder_id}`\n"
        message += f"📝 {reminder['task']}\n"
        message += f"⏰ {time_display}\n"
        message += f"➖➖➖➖➖➖➖\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text("Please provide the reminder ID!\nExample: `/cancel reminder_id`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    
    if chat_id in reminders and reminder_id in reminders[chat_id]:
        try:
            scheduler.remove_job(reminder_id)
        except:
            pass
        
        task = reminders[chat_id][reminder_id]['task']
        del reminders[chat_id][reminder_id]
        save_reminders(reminders)
        
        await update.message.reply_text(f"✅ Reminder cancelled: {task}")
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def done_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text("Please provide the reminder ID!\nExample: `/done reminder_id`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    
    if chat_id in reminders and reminder_id in reminders[chat_id]:
        try:
            scheduler.remove_job(reminder_id)
        except:
            pass
        
        task = reminders[chat_id][reminder_id]['task']
        del reminders[chat_id][reminder_id]
        save_reminders(reminders)
        
        await update.message.reply_text(f"✅ Great job! Task completed: {task}\nReminder stopped.")
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    
    if chat_id in reminders:
        for reminder_id in list(reminders[chat_id].keys()):
            try:
                scheduler.remove_job(reminder_id)
            except:
                pass
        
        reminders[chat_id] = {}
        save_reminders(reminders)
        
        await update.message.reply_text("✅ All reminders have been cancelled!")
    else:
        await update.message.reply_text("📭 You have no active reminders!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("done_"):
        reminder_id = data[5:]
        chat_id = str(query.message.chat_id)
        
        if chat_id in reminders and reminder_id in reminders[chat_id]:
            try:
                scheduler.remove_job(reminder_id)
            except:
                pass
            
            task = reminders[chat_id][reminder_id]['task']
            del reminders[chat_id][reminder_id]
            save_reminders(reminders)
            
            await query.edit_message_text(
                f"✅ Task completed: {task}\nReminder stopped. Great work! 🎉"
            )
        else:
            await query.edit_message_text("❌ This reminder no longer exists!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Global variable for application
application = None

def main():
    global application
    application = Application.builder().token(TOKEN).build()
    
    scheduler.start()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("remind", set_reminder))
    application.add_handler(CommandHandler("list", list_reminders))
    application.add_handler(CommandHandler("cancel", cancel_reminder))
    application.add_handler(CommandHandler("done", done_reminder))
    application.add_handler(CommandHandler("cancelall", cancel_all))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    print(f"Bot @CodexProyBot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
