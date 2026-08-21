"""
Device Fingerprinting & Termux Hardware Extractor.
Ensures stable device characteristics for Instagram API connections.
"""
import hashlib
import os
import shutil
import subprocess
import uuid
from typing import Dict, Any
from instagrapi import Client
from src.utils.console import log_print, log_success, log_warning, fix_persian

# Default known stable bloks_versioning_id for Instagram Android app
DEFAULT_BLOKS_VERSIONING_ID = "ce555e5500576acd8e84a66018f54a05720f2dce29f0bb5a1f97f0c10d6fac48"

# List of modern, realistic Android device profiles for non-Termux environments
STANDARD_DEVICE_POOLS = [
    {
        "app_version": "314.0.0.19.109",
        "android_version": 34,
        "android_release": "14.0",
        "dpi": "480dpi",
        "resolution": "1080x2400",
        "manufacturer": "samsung",
        "device": "e3q",
        "model": "SM-S928B",
        "cpu": "qcom",
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    },
    {
        "app_version": "314.0.0.19.109",
        "android_version": 33,
        "android_release": "13.0",
        "dpi": "450dpi",
        "resolution": "1080x2340",
        "manufacturer": "samsung",
        "device": "dm3q",
        "model": "SM-S918B",
        "cpu": "qcom",
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    },
    {
        "app_version": "314.0.0.19.109",
        "android_version": 34,
        "android_release": "14.0",
        "dpi": "420dpi",
        "resolution": "1080x2400",
        "manufacturer": "Xiaomi",
        "device": "fuxi",
        "model": "2211133G",
        "cpu": "qcom",
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    },
    {
        "app_version": "314.0.0.19.109",
        "android_version": 34,
        "android_release": "14.0",
        "dpi": "440dpi",
        "resolution": "1080x2400",
        "manufacturer": "Google",
        "device": "shiba",
        "model": "Pixel 8",
        "cpu": "tensor-g3",
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    },
    {
        "app_version": "314.0.0.19.109",
        "android_version": 33,
        "android_release": "13.0",
        "dpi": "480dpi",
        "resolution": "1440x3216",
        "manufacturer": "OnePlus",
        "device": "OP515BL1",
        "model": "CPH2449",
        "cpu": "qcom",
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    }
]

def is_running_in_termux() -> bool:
    """Detects if the bot is currently executing inside Termux environment on Android."""
    if "TERMUX_VERSION" in os.environ:
        return True
    if "/com.termux/" in os.environ.get("PREFIX", ""):
        return True
    if os.path.exists("/data/data/com.termux"):
        return True
    if shutil.which("getprop") is not None and not sys_is_pure_linux():
        return True
    return False

def sys_is_pure_linux() -> bool:
    """Checks if current environment is standard desktop/server Linux (not Android)."""
    return not os.path.exists("/system/build.prop") and shutil.which("getprop") is None

def _get_android_prop(prop_name: str, default: str = "") -> str:
    """Helper to query Android system property via getprop."""
    try:
        res = subprocess.run(
            ["getprop", prop_name],
            capture_output=True,
            text=True,
            timeout=1
        )
        val = res.stdout.strip()
        return val if val else default
    except Exception:
        return default

def get_termux_device_properties() -> Dict[str, Any]:
    """Extracts actual hardware and Android OS properties in Termux."""
    manufacturer = _get_android_prop("ro.product.manufacturer", "samsung")
    model = _get_android_prop("ro.product.model", "SM-G998B")
    device = _get_android_prop("ro.product.device", "p3s")
    android_release = _get_android_prop("ro.build.version.release", "13")
    sdk_str = _get_android_prop("ro.build.version.sdk", "33")
    cpu = _get_android_prop("ro.board.platform", "exynos") or _get_android_prop("ro.hardware", "qcom")

    try:
        android_version = int(sdk_str)
    except ValueError:
        android_version = 33

    dpi = "480dpi"
    resolution = "1080x2400"
    try:
        wm_res = subprocess.run(["wm", "size"], capture_output=True, text=True, timeout=1)
        if "Physical size:" in wm_res.stdout:
            resolution = wm_res.stdout.split("Physical size:")[-1].strip()
        wm_density = subprocess.run(["wm", "density"], capture_output=True, text=True, timeout=1)
        if "Physical density:" in wm_density.stdout:
            d_val = wm_density.stdout.split("Physical density:")[-1].strip()
            dpi = f"{d_val}dpi"
    except Exception:
        pass

    return {
        "app_version": "314.0.0.19.109",
        "android_version": android_version,
        "android_release": str(android_release),
        "dpi": dpi,
        "resolution": resolution,
        "manufacturer": manufacturer,
        "device": device,
        "model": model,
        "cpu": cpu,
        "version_code": "563977314",
        "bloks_versioning_id": DEFAULT_BLOKS_VERSIONING_ID
    }

def generate_deterministic_device(username: str) -> Dict[str, Any]:
    """Generates a stable, deterministic device profile based on account username hash."""
    user_hash = hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()
    idx = int(user_hash[:8], 16) % len(STANDARD_DEVICE_POOLS)
    chosen = dict(STANDARD_DEVICE_POOLS[idx])
    return chosen

def generate_deterministic_uuids(username: str) -> Dict[str, str]:
    """Generates deterministic UUIDs and android_device_id from username."""
    user_hash = hashlib.sha256(username.strip().lower().encode("utf-8")).hexdigest()
    android_id = f"android-{user_hash[:16]}"
    phone_id = str(uuid.UUID(user_hash[16:48]))
    device_id = f"android-{user_hash[48:64]}"
    client_session_id = str(uuid.UUID(user_hash[:32]))

    return {
        "android_device_id": android_id,
        "phone_id": phone_id,
        "device_id": device_id,
        "client_session_id": client_session_id
    }

def setup_client_device(client: Client, username: str, session_loaded: bool = False) -> None:
    """Configures instagrapi Client device fingerprinting."""
    if is_running_in_termux():
        props = get_termux_device_properties()
        log_success(f"[bold cyan]Termux Environment Detected:[/bold cyan] Using real Android hardware: [bold green]{props['manufacturer'].capitalize()} {props['model']}[/bold green] (Android {props['android_release']})")
        client.set_device(props)
        if not getattr(client, "bloks_versioning_id", None):
            client.bloks_versioning_id = DEFAULT_BLOKS_VERSIONING_ID
        if not session_loaded or not getattr(client, "android_device_id", None):
            uuids = generate_deterministic_uuids(username)
            client.set_country("US")
            client.set_locale("en_US")
            client.set_timezone_offset(3600 * 3.5)
            client.android_device_id = uuids["android_device_id"]
            client.phone_id = uuids["phone_id"]
            client.device_id = uuids["device_id"]
    else:
        if session_loaded:
            dev = getattr(client, "device", {})
            model = dev.get("model", "Saved Device")
            mfg = dev.get("manufacturer", "Android")
            if not getattr(client, "bloks_versioning_id", None):
                client.bloks_versioning_id = dev.get("bloks_versioning_id", DEFAULT_BLOKS_VERSIONING_ID)
            log_print(f"Loaded persistent device fingerprint: [bold green]{mfg.capitalize()} {model}[/bold green] :mobile_phone:")
        else:
            props = generate_deterministic_device(username)
            uuids = generate_deterministic_uuids(username)
            client.set_device(props)
            if not getattr(client, "bloks_versioning_id", None):
                client.bloks_versioning_id = DEFAULT_BLOKS_VERSIONING_ID
            client.set_country("US")
            client.set_locale("en_US")
            client.set_timezone_offset(3600 * 3.5)
            client.android_device_id = uuids["android_device_id"]
            client.phone_id = uuids["phone_id"]
            client.device_id = uuids["device_id"]
            log_success(f"Configured persistent device fingerprint for @{username}: [bold green]{props['manufacturer'].capitalize()} {props['model']}[/bold green] :mobile_phone:")
