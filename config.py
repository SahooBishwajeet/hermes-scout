import json
from typing import List
import pathlib

def load_data():
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
            return data['target_groups'], data['keywords']
    except FileNotFoundError:
        return [], []

def save_data(groups: List[str], keywords: List[str]):
    with open('data.json', 'w') as f:
        json.dump({
            'target_groups': groups,
            'keywords': keywords
        }, f, indent=4)

# Load initial data
TARGET_GROUPS, KEYWORDS = load_data()

# Time delay between message checks (in seconds)
DELAY: int = 60

# Whether to use user account for historical searches
USE_USER_ACCOUNT = True  # Set to False to use only bot account

# Bot active status
ACTIVE_MONITORING = True
