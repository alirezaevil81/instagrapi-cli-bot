try:
    from src.core.client import Bot, default_challenge_code_handler
except ImportError:
    Bot = None
    default_challenge_code_handler = None

from src.core.device import apply_device_settings, is_termux, DEFAULT_APP_VERSION

__all__ = [
    "Bot",
    "default_challenge_code_handler",
    "apply_device_settings",
    "is_termux",
    "DEFAULT_APP_VERSION",
]
