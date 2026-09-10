#!/usr/bin/env python3
"""
Main Execution Script for Instagram CLI Bot.

Usage:
    python run.py                   # Interactive menu
    python run.py timeline          # Direct launch: Timeline Feed Liker
    python run.py followers         # Direct launch: Following Feed Liker
    python run.py posts             # Direct launch: Post Likers Bot
"""
import os
import sys

# Ensure repository root is on sys.path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def ensure_ready():
    """Performs quick auto-initialization of required files if missing."""
    env_file = os.path.join(ROOT_DIR, ".env")
    comments_file = os.path.join(ROOT_DIR, "comments.json")

    # If first time running and setup hasn't been run, auto-run basic setup
    if not os.path.exists(env_file) or not os.path.exists(comments_file):
        try:
            import setup
            setup.setup_storage()
            setup.setup_env()
            setup.setup_comments()
            setup.setup_database()
        except Exception:
            pass


def main():
    """Launches the bot via the central CLI dispatcher."""
    ensure_ready()
    from src.main import main as run_app
    run_app()


if __name__ == "__main__":
    main()
