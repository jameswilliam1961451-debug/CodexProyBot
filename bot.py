import os
import logging
import json
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable (Render will set this)
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables!")

# Store reminders
reminders_file = 'reminders.json'
scheduler = AsyncIOScheduler(timezone=pytz.UTC)

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
    """Send reminder notification"""
    keyboard = [[InlineKeyboardButton("✅ Mark as Done", callback_data=f"done_{reminder_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # We need to get the application instance - we'll store it globally
        app = application_instance
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ REMINDER: {task}\n\nClick 'Mark as Done' when you complete this task.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Failed to send reminder: {e}")

def schedule_reminder(chat_id, reminder_id, task, reminder_time):
    """Schedule a reminder"""
    trigger = DateTrigger(run_date=reminder_time, timezone=pytz.UTC)
    scheduler.add_job(
        send_reminder,
        trigger,
        args=[chat_id, reminder_id, task],
        id=reminder_id,
        replace_existing=True
    )
    logger.info(f"Scheduled reminder {reminder_id} for {reminder_time}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    welcome_message = """
🤖 *Welcome to CodexProyBot - Reminder Bot!* 🤖

I help you remember your tasks. Here's how to use me:

Commands:
• `/remind [time] [task]` - Set a reminder
  Examples:
  - `/remind 30m Call mom`
  - `/remind 2h Complete report`
  - `/remind 1d Pay bills`

• `/list` - View all your active reminders
• `/cancel [id]` - Cancel a specific reminder
• `/done [id]` - Mark a task as done
• `/cancelall` - Cancel all reminders
• `/help` - Show this help message

Time formats: `30m` (minutes), `2h` (hours), `1d` (days)
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /help is issued."""
    await start(update, context)

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a reminder"""
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text(
            "Please specify time and task!\n\nExample: `/remind 30m Buy groceries`",
            parse_mode='Markdown'
        )
        return
    
    # Parse time and task
    time_str = context.args[0]
    task = ' '.join(context.args[1:])
    
    if not task:
        await update.message.reply_text("Please specify what you want to be reminded about!")
        return
    
    # Parse time
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
    
    # Create reminder ID
    reminder_id = f"{chat_id}_{int(datetime.now().timestamp())}"
    
    # Store reminder
    if chat_id not in reminders:
        reminders[chat_id] = {}
    
    reminders[chat_id][reminder_id] = {
        'task': task,
        'time': reminder_time.isoformat(),
        'created_at': datetime.now(pytz.UTC).isoformat()
    }
    
    save_reminders(reminders)
    
    # Schedule the reminder
    schedule_reminder(chat_id, reminder_id, task, reminder_time)
    
    # Format time for display
    time_display = reminder_time.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    await update.message.reply_text(
        f"✅ Reminder set!\n\n"
        f"📝 Task: {task}\n"
        f"⏰ Time: {time_display}\n"
        f"🆔 ID: `{reminder_id}`\n\n"
        f"I'll remind you then. Mark as done when complete!",
        parse_mode='Markdown'
    )

def parse_time(time_str):
    """Parse time string to datetime"""
    now = datetime.now(pytz.UTC)
    
    # Check for minutes
    if time_str.endswith('m'):
        try:
            minutes = int(time_str[:-1])
            return now + timedelta(minutes=minutes)
        except ValueError:
            return None
    
    # Check for hours
    elif time_str.endswith('h'):
        try:
            hours = int(time_str[:-1])
            return now + timedelta(hours=hours)
        except ValueError:
            return None
    
    # Check for days
    elif time_str.endswith('d'):
        try:
            days = int(time_str[:-1])
            return now + timedelta(days=days)
        except ValueError:
            return None
    
    return None

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all reminders for user"""
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in reminders or not reminders[chat_id]:
        await update.message.reply_text("📭 You have no active reminders!")
        return
    
    message = "📋 *Your Active Reminders:*\n\n"
    for reminder_id, reminder in reminders[chat_id].items():
        time_obj = datetime.fromisoformat(reminder['time'])
        time_display = time_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
        # Show only last 8 characters of ID for brevity
        short_id = reminder_id[-8:]
        message += f"🆔 `{short_id}`\n"
        message += f"📝 {reminder['task']}\n"
        message += f"⏰ {time_display}\n"
        message += f"➖➖➖➖➖➖➖\n"
    
    message += "\nUse `/done full_id` or `/cancel full_id` to manage reminders\n"
    message += "Full ID shown when you set the reminder"
    await update.message.reply_text(message, parse_mode='Markdown')

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a specific reminder"""
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text("Please provide the reminder ID!\nExample: `/cancel reminder_id`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    
    if chat_id in reminders and reminder_id in reminders[chat_id]:
        # Remove from scheduler
        try:
            scheduler.remove_job(reminder_id)
        except Exception as e:
            logger.error(f"Error removing job: {e}")
        
        # Remove from storage
        task = reminders[chat_id][reminder_id]['task']
        del reminders[chat_id][reminder_id]
        save_reminders(reminders)
        
        await update.message.reply_text(f"✅ Reminder cancelled: {task}")
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def done_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark a reminder as done (stop reminder)"""
    chat_id = str(update.effective_chat.id)
    
    if not context.args:
        await update.message.reply_text("Please provide the reminder ID!\nExample: `/done reminder_id`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    
    if chat_id in reminders and reminder_id in reminders[chat_id]:
        # Remove from scheduler
        try:
            scheduler.remove_job(reminder_id)
        except Exception as e:
            logger.error(f"Error removing job: {e}")
        
        # Get task name
        task = reminders[chat_id][reminder_id]['task']
        
        # Remove from storage
        del reminders[chat_id][reminder_id]
        save_reminders(reminders)
        
        await update.message.reply_text(f"✅ Great job! Task completed: {task}\nReminder stopped.")
    else:
        await update.message.reply_text("❌ Reminder not found!")

async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel all reminders for user"""
    chat_id = str(update.effective_chat.id)
    
    if chat_id in reminders:
        # Remove all jobs for this user
        for reminder_id in list(reminders[chat_id].keys()):
            try:
                scheduler.remove_job(reminder_id)
            except Exception as e:
                logger.error(f"Error removing job: {e}")
        
        # Clear reminders
        reminders[chat_id] = {}
        save_reminders(reminders)
        
        await update.message.reply_text("✅ All reminders have been cancelled!")
    else:
        await update.message.reply_text("📭 You have no active reminders!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("done_"):
        reminder_id = data[5:]  # Remove 'done_' prefix
        chat_id = str(query.message.chat_id)
        
        if chat_id in reminders and reminder_id in reminders[chat_id]:
            # Remove from scheduler
            try:
                scheduler.remove_job(reminder_id)
            except Exception as e:
                logger.error(f"Error removing job: {e}")
            
            # Get task name
            task = reminders[chat_id][reminder_id]['task']
            
            # Remove from storage
            del reminders[chat_id][reminder_id]
            save_reminders(reminders)
            
            await query.edit_message_text(
                f"✅ Task completed: {task}\nReminder stopped. Great work! 🎉"
            )
        else:
            await query.edit_message_text("❌ This reminder no longer exists!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# Global variable for application
application_instance = None

async def main():
    """Start the bot"""
    global application_instance
    
    # Create application
    application_instance = Application.builder().token(TOKEN).build()
    
    # Start scheduler
    scheduler.start()
    
    # Add command handlers
    application_instance.add_handler(CommandHandler("start", start))
    application_instance.add_handler(CommandHandler("help", help_command))
    application_instance.add_handler(CommandHandler("remind", set_reminder))
    application_instance.add_handler(CommandHandler("list", list_reminders))
    application_instance.add_handler(CommandHandler("cancel", cancel_reminder))
    application_instance.add_handler(CommandHandler("done", done_reminder))
    application_instance.add_handler(CommandHandler("cancelall", cancel_all))
    
    # Add callback handler for buttons
    application_instance.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    application_instance.add_error_handler(error_handler)
    
    # Start the bot
    print(f"Bot @CodexProyBot is running...")
    await application_instance.initialize()
    await application_instance.start()
    await application_instance.updater.start_polling()
    
    # Keep the bot running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await application_instance.updater.stop()
        await application_instance.stop()
        scheduler.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
