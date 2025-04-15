from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv
import os

load_dotenv()

# Load your API credentials
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\nHere is your session string, add this to your .env file as USER_SESSION:\n")
    print(client.session.save())
