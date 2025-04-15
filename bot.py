import os
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
import config  # Import as module to allow modifications
import pathlib
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
log_dir = pathlib.Path('logs')
log_dir.mkdir(exist_ok=True)

# Configure logging with both file and console handlers
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler (10MB per file, max 5 files)
file_handler = RotatingFileHandler(
    f'logs/bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Load environment variables
load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
USER_SESSION = os.getenv('USER_SESSION', '')

# Initialize clients
bot = TelegramClient('bot_session', API_ID, API_HASH)
user = None
if config.USE_USER_ACCOUNT and USER_SESSION:
    user = TelegramClient(StringSession(USER_SESSION), API_ID, API_HASH)

# Store active users
active_users = set()

async def check_keyword(message_text: str) -> bool:
    if not message_text:
        return False
    return any(keyword.lower() in message_text.lower() for keyword in config.KEYWORDS)

async def format_message(message, chat, sender):
    sender_name = "Unknown"
    if hasattr(sender, 'first_name'):
        sender_name = sender.first_name
    elif hasattr(sender, 'title'):
        sender_name = sender.title

    logger.info(f"Keyword match found in {chat.title} from {sender_name}")
    return f"""
🔍 Keyword Match Found!
👥 Group: {chat.title}
👤 Sender: {sender_name}
🕒 Time: {message.date.strftime('%Y-%m-%d %H:%M:%S')}

📝 Message:
{message.text}

🔗 Link to message: t.me/{chat.username}/{message.id}
"""

async def search_historical_messages(days: int, event):
    logger.info(f"User {event.sender_id} started historical search for {days} days")
    try:
        if not config.USE_USER_ACCOUNT or not user:
            await event.respond("Historical search requires user account access. Please set up USER_SESSION.")
            return

        date_from = datetime.now() - timedelta(days=days)
        total_found = 0

        await event.respond(f"Starting historical search for the last {days} days...")

        async with user:
            for group in config.TARGET_GROUPS:
                async for message in user.iter_messages(group, offset_date=date_from, reverse=True):
                    if await check_keyword(message.text):
                        chat = await user.get_entity(group)
                        sender = await user.get_entity(message.sender_id)
                        forward_text = await format_message(message, chat, sender)

                        await event.respond(forward_text)
                        total_found += 1
                        await asyncio.sleep(1)  # Avoid flooding

        await event.respond(f"Historical search completed. Found {total_found} messages.")

    except Exception as e:
        error_msg = f"Error in historical search: {str(e)}"
        logger.error(error_msg)
        await event.respond(error_msg)

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    logger.info(f"New user started bot: {event.sender_id}")
    active_users.add(event.sender_id)
    await event.respond("""
Welcome to the Message Scraper Bot!

Commands:
/history [days] - Search messages from last N days
/stop - Pause message monitoring
/resume - Resume message monitoring
/status - Check bot status
/keywords - View current keywords
/add_keyword [word] - Add new keyword
/remove_keyword [word] - Remove keyword
/groups - View monitored groups
/add_group [username] - Add new group
/remove_group [username] - Remove group
/help - Show this help message

Live scraping is now active for you!
""")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    await start_handler(event)

@bot.on(events.NewMessage(pattern='/stop'))
async def stop_handler(event):
    logger.info(f"User {event.sender_id} stopped monitoring")
    active_users.discard(event.sender_id)
    await event.respond("Message monitoring paused. Use /resume to start again.")

@bot.on(events.NewMessage(pattern='/resume'))
async def resume_handler(event):
    logger.info(f"User {event.sender_id} resumed monitoring")
    active_users.add(event.sender_id)
    await event.respond("Message monitoring resumed!")

@bot.on(events.NewMessage(pattern='/status'))
async def status_handler(event):
    status = "🟢 Active" if event.sender_id in active_users else "🔴 Paused"
    await event.respond(f"""
Bot Status:
Monitoring: {status}
Groups: {len(config.TARGET_GROUPS)}
Keywords: {len(config.KEYWORDS)}
""")

@bot.on(events.NewMessage(pattern='/keywords'))
async def keywords_handler(event):
    keywords_list = "\n".join([f"• {k}" for k in config.KEYWORDS])
    await event.respond(f"""
Currently monitoring for these keywords:
{keywords_list}
""")

@bot.on(events.NewMessage(pattern=r'/add_keyword\s+(.+)'))
async def add_keyword_handler(event):
    keyword = event.pattern_match.group(1).strip()
    logger.info(f"User {event.sender_id} adding keyword: {keyword}")
    if keyword in config.KEYWORDS:
        await event.respond(f"Keyword '{keyword}' already exists!")
        return
    config.KEYWORDS.append(keyword)
    config.save_data(config.TARGET_GROUPS, config.KEYWORDS)
    await event.respond(f"Added keyword: {keyword}")

@bot.on(events.NewMessage(pattern=r'/remove_keyword\s+(.+)'))
async def remove_keyword_handler(event):
    keyword = event.pattern_match.group(1).strip()
    logger.info(f"User {event.sender_id} removing keyword: {keyword}")
    if keyword not in config.KEYWORDS:
        await event.respond(f"Keyword '{keyword}' not found!")
        return
    config.KEYWORDS.remove(keyword)
    config.save_data(config.TARGET_GROUPS, config.KEYWORDS)
    await event.respond(f"Removed keyword: {keyword}")

@bot.on(events.NewMessage(pattern='/groups'))
async def groups_handler(event):
    groups_list = "\n".join([f"• {g}" for g in config.TARGET_GROUPS])
    await event.respond(f"""
Currently monitoring these groups:
{groups_list}
""")

@bot.on(events.NewMessage(pattern=r'/add_group\s+(.+)'))
async def add_group_handler(event):
    group = event.pattern_match.group(1).strip()
    logger.info(f"User {event.sender_id} adding group: {group}")
    group = group.replace('https://t.me/', '').replace('@', '')
    if group in config.TARGET_GROUPS:
        await event.respond(f"Group '{group}' already exists!")
        return
    try:
        # Verify group exists
        chat = await bot.get_entity(group)
        config.TARGET_GROUPS.append(group)
        config.save_data(config.TARGET_GROUPS, config.KEYWORDS)
        await event.respond(f"Added group: {group}")
    except Exception as e:
        await event.respond(f"Error adding group: {str(e)}")

@bot.on(events.NewMessage(pattern=r'/remove_group\s+(.+)'))
async def remove_group_handler(event):
    group = event.pattern_match.group(1).strip()
    logger.info(f"User {event.sender_id} removing group: {group}")
    group = group.replace('https://t.me/', '').replace('@', '')
    if group not in config.TARGET_GROUPS:
        await event.respond(f"Group '{group}' not found!")
        return
    config.TARGET_GROUPS.remove(group)
    config.save_data(config.TARGET_GROUPS, config.KEYWORDS)
    await event.respond(f"Removed group: {group}")

@bot.on(events.NewMessage(pattern=r'/history(\s+\d+)?'))
async def history_handler(event):
    try:
        days = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 1
        await search_historical_messages(days, event)
    except ValueError:
        await event.respond("Please provide a valid number of days. Example: /history 1")

@bot.on(events.NewMessage(chats=config.TARGET_GROUPS))
async def handle_new_message(event):
    try:
        if await check_keyword(event.message.text):
            chat = await event.get_chat()
            sender = await event.get_sender()
            forward_text = await format_message(event.message, chat, sender)

            # Send to all active users
            for user_id in active_users:
                await bot.send_message(user_id, forward_text)
            logger.info(f"Live message forwarded from {chat.title}")

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

async def main():
    try:
        logger.info("Bot started")
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("Bot is now active and monitoring messages!")
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")

if __name__ == '__main__':
    asyncio.run(main())
