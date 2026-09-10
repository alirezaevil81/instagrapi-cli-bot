#!/usr/bin/env python3
"""
Setup and Initialization Script for Instagram CLI Bot.

Universal initialization script:
- Creates required storage directories (sessions, database, logs)
- Initializes configuration (.env from .env.example)
- Initializes comments file (comments.json from comments.example.json)
- Initializes SQLite database schema
- Verifies python dependencies

Usage:
    python setup.py
"""
import os
import sys
import shutil
import importlib.util

# Add current directory to path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)


def print_step(title: str):
    print(f"\n[+] {title}")


def print_success(msg: str):
    print(f"  \033[92m✔\033[0m {msg}")


def print_info(msg: str):
    print(f"  \033[94mℹ\033[0m {msg}")


def print_warn(msg: str):
    print(f"  \033[93m⚠\033[0m {msg}")


def print_error(msg: str):
    print(f"  \033[91m✖\033[0m {msg}")


def setup_storage():
    """Create storage directories and ensure .gitignore markers exist."""
    print_step("Setting up storage directories")
    storage_subdirs = [
        "storage/sessions",
        "storage/database",
        "storage/logs",
    ]
    for rel_dir in storage_subdirs:
        dir_path = os.path.join(BASE_DIR, rel_dir)
        os.makedirs(dir_path, exist_ok=True)
        gitignore_path = os.path.join(dir_path, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as gf:
                gf.write("*\n!.gitignore\n")
        print_success(f"Directory ready: {rel_dir}/")


def setup_env():
    """Copy .env.example to .env if .env does not exist."""
    print_step("Setting up environment configuration (.env)")
    env_example = os.path.join(BASE_DIR, ".env.example")
    env_target = os.path.join(BASE_DIR, ".env")

    if not os.path.exists(env_example):
        print_warn(".env.example template not found. Skipping .env creation.")
        return

    if not os.path.exists(env_target):
        shutil.copyfile(env_example, env_target)
        print_success("Created .env from .env.example")
    else:
        print_info(".env file already exists. Kept existing file.")


def setup_comments():
    """Copy comments.example.json to comments.json if comments.json does not exist."""
    print_step("Setting up comments configuration (comments.json)")
    comments_example = os.path.join(BASE_DIR, "comments.example.json")
    comments_target = os.path.join(BASE_DIR, "comments.json")

    if not os.path.exists(comments_example):
        print_warn("comments.example.json template not found. Creating default comments.json.")
        import json
        default_comments = [
            "Awesome post! 🔥",
            "Great content! ❤️",
            "Love this! 👏",
            "Amazing capture 😍",
            "Incredible vibes ✨"
        ]
        with open(comments_target, "w", encoding="utf-8") as f:
            json.dump(default_comments, f, ensure_ascii=False, indent=2)
        print_success("Created default comments.json")
        return

    if not os.path.exists(comments_target):
        shutil.copyfile(comments_example, comments_target)
        print_success("Created comments.json from template")
    else:
        print_info("comments.json already exists. Kept existing file.")


def setup_database():
    """Initialize SQLite database tables."""
    print_step("Initializing SQLite database")
    try:
        from src.database.engine import init_db
        init_db()
        print_success("Database schema initialized successfully")
    except Exception as e:
        print_warn(f"Could not initialize database yet: {e}")


def check_dependencies():
    """Verify essential dependencies."""
    print_step("Checking required packages")
    required = [
        ("instagrapi", "instagrapi"),
        ("questionary", "questionary"),
        ("rich", "rich"),
    ]
    missing = []
    for mod_name, pkg_name in required:
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)
        else:
            print_success(f"Installed: {pkg_name}")

    if missing:
        print_warn(f"Missing dependencies: {', '.join(missing)}")
        print_info(f"Install them via: pip install {' '.join(missing)}")
    else:
        print_success("All core dependencies are installed and ready!")


def run_setup():
    """Execute all setup tasks."""
    print("=" * 65)
    print(" Instagram CLI Bot - Environment & Workspace Setup")
    print("=" * 65)

    setup_storage()
    setup_env()
    setup_comments()
    setup_database()
    check_dependencies()

    print("\n" + "=" * 65)
    print(" \033[92mSetup completed successfully!\033[0m")
    print(" You can now run the bot using:")
    print("   \033[96muv run instabot\033[0m")
    print("   or   \033[96mpython src/main.py\033[0m")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_setup()
