"""
Device Fingerprinting and Hardware Emulation.
Provides hardware profiles compatible with instagrapi and Termux/Android.
Extracts real physical Android device hardware properties in Termux via getprop and wm size.
Lets instagrapi automatically manage official app versions, version codes, and Bloks hashes.
"""
import os
import re
import platform
import subprocess
from typing import Dict, Any, Optional

# Cached hardware settings so repeated calls are instantaneous
_CACHED_HARDWARE: Optional[Dict[str, Any]] = None
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
            match = re.search(r"(\d{3,4})x(\d{3,4})", res.stdout)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                w_port, h_port = min(w, h), max(w, h)
                return f"{w_port}x{h_port}"
    except Exception:
        pass
    return default


def get_screen_density(default: str = "420dpi") -> str:
    """Queries actual screen density (DPI) from Android system properties."""
    dpi_raw = get_android_prop("ro.sf.lcd_density", "")
    if dpi_raw and dpi_raw.isdigit():
        return f"{dpi_raw}dpi"
    return default


def get_android_sdk_level() -> str:
    """Detects Android API / SDK level on Termux devices using getprop."""
    sdk = os.getenv("ANDROID_API_LEVEL")
    if sdk and sdk.strip().isdigit():
        return sdk.strip()
    return get_android_prop("ro.build.version.sdk", "34")


def get_android_release_version() -> str:
    """Detects Android OS release version (e.g. '13', '14', '15')."""
    return get_android_prop("ro.build.version.release", "14")


def get_real_device_info() -> Dict[str, Any]:
    """
    Extracts authentic device hardware specifications from the current Android phone in Termux.
    Contains ONLY hardware parameters so instagrapi handles its official app version automatically.
    """
    global _CACHED_HARDWARE, _CACHED_IS_REAL_HARDWARE

    if _CACHED_HARDWARE is not None:
        return dict(_CACHED_HARDWARE)

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

        if manufacturer_raw and model_raw:
            mfg = manufacturer_raw.capitalize() if manufacturer_raw.islower() else manufacturer_raw
            model = model_raw.strip()
            device_name = device_raw.strip() or model.lower().replace(" ", "_")
            cpu = cpu_raw.strip() or "qcom"
            sdk_int = int(sdk_raw) if sdk_raw.isdigit() else 34

            hardware = {
                "manufacturer": mfg,
                "model": model,
                "device": device_name,
                "cpu": cpu,
                "android_version": sdk_int,
                "android_release": release_raw or "14",
                "dpi": dpi,
                "resolution": resolution,
            }
            _CACHED_HARDWARE = hardware
            _CACHED_IS_REAL_HARDWARE = True
            return dict(hardware)

    _CACHED_IS_REAL_HARDWARE = False
    return {}


def format_device_summary(device_info: Dict[str, Any]) -> str:
    """Returns a clean single-line description of the active device profile."""
    if not device_info:
        return "Default Device Profile"
    mfg = device_info.get("manufacturer", "Android")
    model = device_info.get("model", "Device")
    rel = device_info.get("android_release", "")
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
    if _CACHED_HARDWARE is None and is_termux():
        get_real_device_info()
    return _CACHED_IS_REAL_HARDWARE


def get_recommended_device() -> Dict[str, Any]:
    """
    Returns real hardware specs in Termux, or an empty dict to use instagrapi defaults.
    """
    return get_real_device_info()


def apply_device_settings(client: Any) -> None:
    """
    Configures device hardware profile on an instagrapi Client instance.
    Calls client.set_device(hardware_updates) which overlays ONLY the physical hardware specs,
    allowing instagrapi to automatically manage official app versions, version codes,
    bloks hashes, and user agents without version conflicts.
    """
    if is_termux():
        hardware = get_real_device_info()
        if hardware:
            if hasattr(client, "set_device"):
                try:
                    client.set_device(hardware)
                except Exception:
                    if hasattr(client, "device_settings") and isinstance(client.device_settings, dict):
                        client.device_settings.update(hardware)
            elif hasattr(client, "device_settings") and isinstance(client.device_settings, dict):
                client.device_settings.update(hardware)
