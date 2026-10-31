"""
Configuration settings for the Twitch Username Checker.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "results.db"

# Twitch API Endpoints
TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_INTEGRITY_URL = "https://gql.twitch.tv/integrity"

# Public Web Client IDs used by Twitch web clients
CLIENT_IDS = [
    "kimne78kx3ncx6brgo4mv6wki5h1ko",  # Primary web client
    "ue6666qo983tsx6so1t0vnau1akhzm",
    "b31o4qgahfgdgdtbj9x6xwvjm8xz2a",
]

DEFAULT_CLIENT_ID = CLIENT_IDS[0]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

DEFAULT_USER_AGENT = USER_AGENTS[0]

# Batch limits (Conservative safe boundaries tested against Twitch GQL limits)
BATCH_ITEMS_PER_REQ = 20    # GQL array batch size (max is 35)
ALIASES_PER_ITEM = 10       # Root field aliases per query (max is 15)
NAMES_PER_REQUEST = BATCH_ITEMS_PER_REQ * ALIASES_PER_ITEM  # 200 names / HTTP request!

# Twitch username rules (Strictly 4 to 25 characters)
MIN_USERNAME_LENGTH = 4
MAX_USERNAME_LENGTH = 25
RESERVED_USERNAMES = {
    "twitch", "admin", "administrator", "root", "support", "help", "security",
    "moderator", "mod", "staff", "system", "null", "undefined", "anonymous",
    "api", "graphql", "stream", "video", "broadcast", "channel"
}
