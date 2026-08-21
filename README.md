<div align="center">

<img src="https://img.icons8.com/3d-fluent/100/robot-6.png" alt="Instagram CLI Bot" width="80" height="80" />

# Instagram CLI Bot

**A sleek, modular, and interactive Instagram automation tool powered by `instagrapi` & `rich`.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-Astral-DE5FE9?style=flat-square&logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Rich](https://img.shields.io/badge/Terminal-Rich%20%7C%20Questionary-00A896?style=flat-square)](https://rich.readthedocs.io/)
[![Platform](https://img.shields.io/badge/OS-Windows%20%7C%20Linux%20%7C%20Android-green?style=flat-square)]()
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

[Quick Start](#-quick-start) • [Features](#-features) • [Android (Termux)](#-android--termux) • [Configuration](#-configuration)

</div>

---

## ⚡ Quick Start

### 1. With `uv` *(Recommended)*
```bash
git clone https://github.com/alirezaevil81/instagrapi-cli-bot.git
cd instagrapi-cli-bot

uv sync
uv run instabot
```

### 2. With `pip`
```bash
git clone https://github.com/alirezaevil81/instagrapi-cli-bot.git
cd instagrapi-cli-bot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install .
python src/main.py
```

---

## ✨ Features

- **Interactive Session Picker**: Switch between saved sessions (`data/json/`) via arrow keys, or add new accounts.
- **Smart 2FA & Masked Passwords**: Native handling for Two-Factor Authentication (SMS / Authenticator / Backup codes).
- **Dynamic Live Timers**: Animated spinners, progress bars, and real-time second countdowns during safety cooldowns.
- **Following Engagement**: Automatically track and interact with your following list's newest posts.
- **Target Post Likers**: Extract likers from target posts with automatic privacy and already-following filters.
- **Persian & RTL Reshaping**: Integrated bidirectional text rendering for smooth terminal typography.

---

## 📱 Android / Termux

Run the bot directly on your Android device:

```bash
# 1. Install prerequisites
pkg update -y && pkg install python git clang binutils libjpeg-turbo zlib freetype libffi openssl -y

# 2. Clone repository & enter directory
git clone https://github.com/alirezaevil81/instagrapi-cli-bot.git
cd instagrapi-cli-bot

# 3. Create venv & install pre-compiled pydantic-core (No Rust compilation needed)
python -m venv .venv
source .venv/bin/activate
pip install pydantic-core --extra-index-url https://eutalix.github.io/android-pydantic-core/
pip install .

# 4. Start the bot
python src/main.py
```

> **💡 Background Mode:** Run `termux-wake-lock` to prevent Android from sleeping while the bot is active.

---

## ⚙️ Configuration

Custom parameters available before starting any task:

| Setting | Default | Description |
| :--- | :---: | :--- |
| **Like Delay** | `30s` – `60s` | Random cooldown interval after liking a post |
| **Comment Delay** | `60s` – `90s` | Random interval between posting comments |
| **Posts Per User** | `3` – `4` | Number of recent public media items to inspect |
| **User Cooldown** | `2 min` | Rest period after completing engagement with an account |
| **Cycle Cooldown** | `1 hour` | Rest duration after processing the entire queue |
| **API Request Delay** | `3s` – `7s` | Base delay between general Instagram API queries |

---

<details>
<summary><b>📂 Project Structure</b> (Click to expand)</summary>

```text
instagrapi-cli-bot/
├── src/
│   ├── main.py                  # CLI Menu Hub & interactive launcher
│   ├── config.py                # Central storage paths & comment constants
│   ├── core/                    # Core engine & device identity
│   │   ├── __init__.py
│   │   ├── client.py            # Instagram client, 2FA, session & warm-up actions
│   │   └── device.py            # Termux hardware & persistent device fingerprinting
│   ├── database/                # Dedicated SQLite database layer
│   │   ├── __init__.py
│   │   ├── engine.py            # SQLite connection pooling & migrations
│   │   └── repository.py        # Target queue & audit history CRUD
│   ├── services/                # Automated engagement workflows
│   │   ├── __init__.py
│   │   ├── followers_liker.py   # Following engagement service
│   │   └── post_liker.py        # Post likers extraction & engagement service
│   └── utils/                   # Rich console, logging & signals
│       ├── __init__.py
│       ├── console.py           # Rich timers, tables, banners & RTL support
│       ├── logger.py            # Clean rotating file logger
│       └── signals.py           # Graceful shutdown handler (Ctrl+C / SIGTERM)
├── storage/                     # Isolated persistent data directory
│   ├── sessions/                # Saved Instagram account sessions (.json)
│   ├── database/                # SQLite database files (bot.db)
│   └── logs/                    # Rotating log files (bot.log)
├── pyproject.toml               # Modern packaging & CLI command entrypoints
└── README.md
```
</details>

---

## ⚠️ Disclaimer

This tool is intended for **educational and personal automation purposes**. Please comply with Instagram's Terms of Service and utilize realistic, safe delay intervals.

---

<div align="center">
<sub>Built with precision by <a href="https://github.com/alirezaevil81">alirezaevil81</a></sub>
</div>
