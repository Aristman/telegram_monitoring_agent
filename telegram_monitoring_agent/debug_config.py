#!/usr/bin/env python3
"""
Debug script to test configuration loading
"""

import os
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
os.chdir(current_dir)

print("Current working directory:", os.getcwd())
print("Environment file exists:", Path(".env").exists())

if Path(".env").exists():
    with open(".env", "r", encoding="utf-8") as f:
        print("Environment file contents:")
        print(f.read())
        print("---")

print("Environment variables:")
for key, value in os.environ.items():
    if key.startswith(("MONITORED_", "YANDEX_", "TELEGRAM_", "WIKI_", "DB_", "DAILY_", "TIMEZONE", "LOG_", "TEMP_", "DEBUG")):
        print(f"{key}={value}")

print("\nTrying to import config...")
try:
    from config import AppConfig
    print("Config imported successfully")

    print("Creating AppConfig instance...")
    config = AppConfig()
    print("AppConfig created successfully")

    print(f"Monitored chats: {config.monitored_chats}")
    print(f"Monitored chats list: {config.monitored_chats_list}")
    print(f"Message collection interval: {config.message_collection_interval}")
    print(f"Debug mode: {config.debug}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()