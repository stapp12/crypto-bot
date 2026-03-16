"""
group_manager.py
שומר ומנהל את רשימת הקבוצות אוטומטית.
הבוט מתווסף לקבוצה → נשמר. מוסר מהקבוצה → נמחק.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GROUPS_FILE = Path("groups.json")


def load_groups() -> dict[int, str]:
    """טוען את הקבוצות מהקובץ. מחזיר {chat_id: title}"""
    if not GROUPS_FILE.exists():
        return {}
    try:
        data = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
        return {int(k): v for k, v in data.items()}
    except Exception as e:
        log.error(f"Failed to load groups: {e}")
        return {}


def save_groups(groups: dict[int, str]):
    """שומר את הקבוצות לקובץ."""
    try:
        GROUPS_FILE.write_text(
            json.dumps(groups, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        log.error(f"Failed to save groups: {e}")


def add_group(groups: dict[int, str], chat_id: int, title: str):
    if chat_id not in groups:
        groups[chat_id] = title
        save_groups(groups)
        log.info(f"✅ Group added: {title} ({chat_id})")


def remove_group(groups: dict[int, str], chat_id: int):
    if chat_id in groups:
        title = groups.pop(chat_id)
        save_groups(groups)
        log.info(f"❌ Group removed: {title} ({chat_id})")
