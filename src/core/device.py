"""
Device Fingerprinting and Hardware Emulation.
Provides device settings and hardware profiles compatible with instagrapi 3.0+ and Termux/Android/Linux.
"""
import os
import platform
import subprocess
from typing import Dict, Any

# Instagram 3.0+ default Android profile constants
DEFAULT_APP_VERSION = "446.0.0.49.77"
DEFAULT_VERSION_CODE = "446000049"

def is_termux() -> bool:
    """Checks if currently executing inside Android Termux environment."""
    return bool(
        os.path.exists("/data/data/com.termux")
        or os.getenv("TERMUX_VERSION")
        or "com.termux" in os.getenv("PREFIX", "")
    )

def get_android_sdk_level() -> str:
    """Detects Android API / SDK level on Termux devices using getprop."""
    sdk = os.getenv("ANDROID_API_LEVEL")
    if sdk:
        return sdk
    if is_termux():
        try:
            res = subprocess.run(["getprop", "ro.build.version.sdk"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                return res.stdout.strip()
        except Exception:
            pass
    return "33"  # Android 13 default

def get_recommended_device() -> Dict[str, Any]:
    """
    Returns an authentic Android device fingerprint matching modern Instagram client standards.
    """
    sdk = get_android_sdk_level()
    return {
        "app_version": DEFAULT_APP_VERSION,
        "android_version": 33 if sdk == "33" else int(sdk) if sdk.isdigit() else 33,
        "android_release": "13",
        "dpi": "420dpi",
        "resolution": "1080x2400",
        "manufacturer": "Google",
        "device": "cheetah",
        "model": "Pixel 7 Pro",
        "cpu": "tensor",
        "version_code": DEFAULT_VERSION_CODE,
    }

def apply_device_settings(client: Any) -> None:
    """
    Configures device and app profile on an instagrapi Client instance.
    Uses instagrapi 3.0's set_app() when available, falling back to set_device().
    """
    # 1. Apply modern app version profile in instagrapi 3.0+
    if hasattr(client, "set_app"):
        try:
            client.set_app(DEFAULT_APP_VERSION)
        except Exception:
            pass

    # 2. Configure device fingerprint if device_settings is empty
    if hasattr(client, "device_settings") and not client.device_settings:
        recommended = get_recommended_device()
        if hasattr(client, "set_device"):
            try:
                client.set_device(recommended)
            except Exception:
                client.device_settings = recommended
        else:
            client.device_settings = recommended
