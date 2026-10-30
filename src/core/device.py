"""
Device Fingerprinting and Hardware Emulation.
Provides device settings and hardware profiles compatible with instagrapi 3.0+ and Termux/Android/Linux.
Extracts real physical Android device hardware properties in Termux via getprop and wm size.
"""
import os
import re
import platform
import subprocess
from typing import Dict, Any, Optional

# Instagram 3.0+ default Android profile constants
DEFAULT_APP_VERSION = "446.0.0.49.77"
DEFAULT_VERSION_CODE = "446000049"

# Cached device settings so repeated calls are instantaneous
_CACHED_DEVICE_SETTINGS: Optional[Dict[str, Any]] = None
_CACHED_IS_REAL_HARDWARE: bool = False


def is_termux() -> bool:
    """Checks if currently executing inside Android Termux environment."""
    return bool(
        os.path.exists("/data/data/com.termux")
        or os.getenv("TERMUX_VERSION")
        or "com.termux" in os.getenv("PREFIX", "")
    )


def get_android_prop(prop_name: str, default: str = "") -> str:
    """
    Safely queries an Android system property via getprop CLI.
    Available across all Android devices in Termux without root privileges.
    """
    if not is_termux():
        return default
    try:
        res = subprocess.run(
            ["getprop", prop_name],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False
        )
        if res.returncode == 0:
            val = res.stdout.strip()
            if val:
                return val
    except Exception:
        pass
    return default


def get_screen_resolution(default: str = "1080x2400") -> str:
    """
    Queries actual physical screen resolution via Android WindowManager (wm size).
    Returns formatted string like '1080x2400'.
    """
    if not is_termux():
        return default
    try:
        res = subprocess.run(
            ["wm", "size"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False
        )
        if res.returncode == 0 and res.stdout:
            # Matches 'Physical size: 1080x2400' or 'Override size: ...'
            match = re.search(r"(\d{3,4})x(\d{3,4})", res.stdout)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                # Ensure portrait orientation (smaller x larger)
                w_port, h_port = min(w, h), max(w, h)
                return f"{w_port}x{h_port}"
    except Exception:
        pass
    return default


def get_screen_density(default: str = "420dpi") -> str:
    """
    Queries actual screen density (DPI) from Android system properties.
    """
    dpi_raw = get_android_prop("ro.sf.lcd_density", "")
    if dpi_raw and dpi_raw.isdigit():
        return f"{dpi_raw}dpi"
    return default


def get_android_sdk_level() -> str:
    """Detects Android API / SDK level on Termux devices using getprop."""
    sdk = os.getenv("ANDROID_API_LEVEL")
    if sdk and sdk.strip().isdigit():
        return sdk.strip()
    return get_android_prop("ro.build.version.sdk", "33")


def get_android_release_version() -> str:
    """Detects Android OS release version (e.g. '13', '14', '15')."""
    return get_android_prop("ro.build.version.release", "13")


def get_real_device_info() -> Dict[str, Any]:
    """
    Extracts authentic device hardware specifications from the current Android phone in Termux.
    If not running on Termux or if system properties cannot be read, falls back to modern defaults.
    """
    global _CACHED_DEVICE_SETTINGS, _CACHED_IS_REAL_HARDWARE

    if _CACHED_DEVICE_SETTINGS is not None:
        return dict(_CACHED_DEVICE_SETTINGS)

    if is_termux():
        manufacturer_raw = get_android_prop("ro.product.manufacturer", "")
        model_raw = get_android_prop("ro.product.model", "")
        brand_raw = get_android_prop("ro.product.brand", "")
        device_raw = get_android_prop("ro.product.device", "") or get_android_prop("ro.product.name", "")
        cpu_raw = get_android_prop("ro.board.platform", "") or get_android_prop("ro.hardware", "")
        sdk_raw = get_android_sdk_level()
        release_raw = get_android_release_version()
        dpi = get_screen_density("420dpi")
        resolution = get_screen_resolution("1080x2400")

        # If we successfully retrieved phone manufacturer and model from real hardware
        if manufacturer_raw and model_raw:
            # Normalize casing (e.g. 'samsung' -> 'Samsung', 'xiaomi' -> 'Xiaomi')
            mfg = manufacturer_raw.capitalize() if manufacturer_raw.islower() else manufacturer_raw
            model = model_raw.strip()
            device_name = device_raw.strip() or model.lower().replace(" ", "_")
            cpu = cpu_raw.strip() or "qcom"
            sdk_int = int(sdk_raw) if sdk_raw.isdigit() else 33

            settings = {
                "app_version": DEFAULT_APP_VERSION,
                "android_version": sdk_int,
                "android_release": release_raw or "13",
                "dpi": dpi,
                "resolution": resolution,
                "manufacturer": mfg,
                "device": device_name,
                "model": model,
                "cpu": cpu,
                "version_code": DEFAULT_VERSION_CODE,
            }
            _CACHED_DEVICE_SETTINGS = settings
            _CACHED_IS_REAL_HARDWARE = True
            return dict(settings)

    # Fallback to recommended modern profile
    sdk_int = int(get_android_sdk_level()) if get_android_sdk_level().isdigit() else 33
    settings = {
        "app_version": DEFAULT_APP_VERSION,
        "android_version": sdk_int,
        "android_release": "13",
        "dpi": "420dpi",
        "resolution": "1080x2400",
        "manufacturer": "Google",
        "device": "cheetah",
        "model": "Pixel 7 Pro",
        "cpu": "tensor",
        "version_code": DEFAULT_VERSION_CODE,
    }
    _CACHED_DEVICE_SETTINGS = settings
    _CACHED_IS_REAL_HARDWARE = False
    return dict(settings)


def format_device_summary(device_info: Dict[str, Any]) -> str:
    """Returns a clean single-line description of the active device profile."""
    mfg = device_info.get("manufacturer", "Unknown")
    model = device_info.get("model", "Device")
    rel = device_info.get("android_release", "Android")
    res = device_info.get("resolution", "")
    dpi = device_info.get("dpi", "")
    details = []
    if rel:
        details.append(f"Android {rel}")
    if res:
        details.append(res)
    if dpi:
        details.append(dpi)
    det_str = f" ({', '.join(details)})" if details else ""
    return f"{mfg} {model}{det_str}"


def is_real_phone_hardware() -> bool:
    """Returns True if the current device profile was extracted from real Android hardware."""
    global _CACHED_IS_REAL_HARDWARE
    if _CACHED_DEVICE_SETTINGS is None:
        get_real_device_info()
    return _CACHED_IS_REAL_HARDWARE


def get_recommended_device() -> Dict[str, Any]:
    """
    Returns an authentic Android device fingerprint matching modern Instagram client standards.
    Uses real phone hardware in Termux when available.
    """
    return get_real_device_info()


def apply_device_settings(client: Any) -> None:
    """
    Configures device and app profile on an instagrapi Client instance.
    Uses instagrapi 3.0's set_app() when available, falling back to set_device().
    In Termux, extracts and applies the phone's genuine hardware specs.
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
