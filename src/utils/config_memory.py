"""
Smart Memory & Preferences Manager.
Saves, retrieves, and remembers user configuration choices across bot sessions,
enabling 1-click Quick Launch and Back navigation.
"""
import os
import json
from typing import Optional, Tuple, Any

from src.config import STORAGE_DIR
from src.utils.console import console, em, show_stats_card, QUESTIONARY_STYLE

PREFS_FILE = os.path.join(STORAGE_DIR, "bot_preferences.json")


def _load_all_prefs() -> dict:
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_all_prefs(prefs: dict) -> None:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_bot_preferences(service_key: str, data: dict) -> None:
    """Saves the last used configuration for a specific bot service."""
    prefs = _load_all_prefs()
    prefs[service_key] = data
    prefs["__last_service__"] = service_key
    _save_all_prefs(prefs)


def get_bot_preferences(service_key: str) -> Optional[dict]:
    """Retrieves saved configuration for a specific bot service."""
    prefs = _load_all_prefs()
    return prefs.get(service_key)


def get_last_used_service() -> Optional[str]:
    """Returns the key of the last executed bot service."""
    prefs = _load_all_prefs()
    return prefs.get("__last_service__")


def prompt_config_mode(service_name: str, service_key: str) -> Tuple[str, Optional[dict]]:
    """
    Presents a smart start menu offering 1-click Quick Launch if previous configuration is found,
    or Custom Configuration / Back navigation.
    Returns:
        ("quick", saved_config_dict)
        ("custom", None)
        ("back", None)
    """
    import questionary
    saved = get_bot_preferences(service_key)
    kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}

    if saved and isinstance(saved, dict):
        # Format human-readable summary of saved preferences
        summary = {}
        for k, v in saved.items():
            if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                summary[f":stopwatch: {k}"] = f"[bold cyan]{v[0]}-{v[1]}s[/bold cyan]"
            elif isinstance(v, bool):
                summary[f":pushpin: {k}"] = "[green]Enabled[/green]" if v else "[red]Disabled[/red]"
            else:
                summary[f":star: {k}"] = f"[bold white]{v}[/bold white]"

        show_stats_card(
            f"Last Saved Config for {service_name}",
            summary,
            border_style="cyan"
        )

        choice = questionary.select(
            em(f"How would you like to configure {service_name}?"),
            choices=[
                questionary.Choice(
                    title=em(":rocket: 1. Quick Launch (شروع فوری با آخرین تنظیمات ذخیره‌شده)"),
                    value="quick"
                ),
                questionary.Choice(
                    title=em(":gear: 2. Customize Settings (تغییر و شخصی‌سازی تنظیمات)"),
                    value="custom"
                ),
                questionary.Choice(
                    title=em(":back: 3. Back to Main Menu (بازگشت به منوی اصلی)"),
                    value="back"
                ),
            ],
            **kwargs
        ).ask()

        if choice == "quick":
            return "quick", saved
        elif choice == "back" or choice is None:
            return "back", None
        else:
            return "custom", None
    else:
        choice = questionary.select(
            em(f"Configure {service_name}:"),
            choices=[
                questionary.Choice(
                    title=em(":gear: 1. Configure Bot Parameters (شروع تنظیمات)"),
                    value="custom"
                ),
                questionary.Choice(
                    title=em(":back: 2. Back to Main Menu (بازگشت به منوی اصلی)"),
                    value="back"
                ),
            ],
            **kwargs
        ).ask()

        if choice == "back" or choice is None:
            return "back", None
        return "custom", None
