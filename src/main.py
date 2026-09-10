import os
import sys

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import questionary
from src.database.engine import init_db
from src.utils.console import show_banner, console, em, show_config_tree, show_system_dashboard, show_markdown
from src.utils.signals import register_graceful_shutdown
from src.services.followers_liker import main as run_followers_bot
from src.services.post_liker import main as run_post_likers_bot
from src.services.timeline_liker import main as run_timeline_bot

def main():
    """Interactive CLI menu to select and launch bots."""
    init_db()
    register_graceful_shutdown()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().strip()
        if arg in ["timeline", "feed", "1"]:
            run_timeline_bot()
            return
        elif arg in ["followers", "following", "2"]:
            run_followers_bot()
            return
        elif arg in ["posts", "post_likers", "likers", "3"]:
            run_post_likers_bot()
            return

    show_banner("Instagram Bot Hub", "Select bot mode to run & automate your Instagram actions")
    
    welcome_text = """
### Welcome to Instagrapi CLI Bot 🚀

This is your central hub for automating Instagram engagement safely and efficiently.
* **Safe & Human-like:** All delays and actions simulate real user behavior.
* **2FA Support:** Fully supports accounts with Two-Factor Authentication.
* **Smart Filtering:** Built-in SQLite queues ensure you never duplicate interactions.

Choose a module below to get started!
"""
    show_markdown(welcome_text)
    
    show_system_dashboard()
    show_config_tree()

    choice = questionary.select(
        em("Select bot mode to run:"),
        choices=[
            questionary.Choice(
                title=em(":newspaper: 1. Timeline Feed Liker (Continuous Feed Liker with Auto-Refresh)"),
                value="timeline"
            ),
            questionary.Choice(
                title=em(":busts_in_silhouette: 2. Following Feed Liker (Automated Liker for Accounts You Follow)"),
                value="followers"
            ),
            questionary.Choice(
                title=em(":target: 3. Post Likers Bot (Extract Likers & Automated Engagement)"),
                value="posts"
            ),
            questionary.Choice(
                title=em(":door: 4. Exit"),
                value="exit"
            ),
        ]
    ).ask()

    if choice == "timeline":
        run_timeline_bot()
    elif choice == "followers":
        run_followers_bot()
    elif choice == "posts":
        run_post_likers_bot()
    else:
        console.print(em("\n[bold yellow]:wave: Exited successfully. Goodbye![/bold yellow]\n"))


if __name__ == "__main__":
    main()
