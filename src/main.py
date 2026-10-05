import os
import sys

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import questionary
from src.database.engine import init_db
from src.utils.console import (
    show_banner,
    console,
    em,
    show_config_tree,
    show_system_dashboard,
    show_markdown,
    QUESTIONARY_STYLE,
)
from src.utils.notifier import ensure_termux_api
from src.utils.config_memory import get_last_used_service
from src.utils.signals import register_graceful_shutdown
from src.services.followers_liker import main as run_followers_bot
from src.services.post_liker import main as run_post_likers_bot
from src.services.timeline_liker import main as run_timeline_bot
from src.services.comment_liker import main as run_comment_likers_bot

def main():
    """Interactive CLI menu to select and launch bots."""
    init_db()
    register_graceful_shutdown()
    ensure_termux_api(interactive=True)

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
        elif arg in ["comments", "comment_liker", "comment_likers", "4"]:
            run_comment_likers_bot()
            return

    while True:
        show_banner("Instagram Automation Hub", "Smart, Safe, High-Performance Engagement Engine")
        show_system_dashboard()

        last_service = get_last_used_service()
        service_names = {
            "timeline_liker": "Timeline Feed Liker",
            "followers_liker": "Following Feed Liker",
            "post_liker": "Post Likers Bot",
            "comment_liker": "Post Comments Liker"
        }

        choices = []
        if last_service and last_service in service_names:
            choices.append(
                questionary.Choice(
                    title=em(f":zap: 0. Quick Run Last Bot: [bold cyan]{service_names[last_service]}[/bold cyan]"),
                    value=f"last_{last_service}"
                )
            )

        choices.extend([
            questionary.Choice(
                title=em(":newspaper: 1. Timeline Feed Liker (Continuous Home Feed Liker with Live Refresh)"),
                value="timeline"
            ),
            questionary.Choice(
                title=em(":busts_in_silhouette: 2. Following Feed Liker (Smart Engagement for Accounts You Follow)"),
                value="followers"
            ),
            questionary.Choice(
                title=em(":target: 3. Post Likers Bot (Extract Target Likers & Sequential Engagement)"),
                value="posts"
            ),
            questionary.Choice(
                title=em(":speech_balloon: 4. Post Comments Liker (0-Like Comments + Optional Posts & Story View/Like)"),
                value="comments"
            ),
            questionary.Choice(
                title=em(":gear: 5. View System Configuration (Inspect Storage, Delays & Comments Templates)"),
                value="config"
            ),
            questionary.Choice(
                title=em(":door: 6. Exit"),
                value="exit"
            ),
        ])

        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        choice = questionary.select(
            em("Select bot mode to run:"),
            choices=choices,
            **kwargs
        ).ask()

        if choice is None or choice == "exit":
            console.print(em("\n[bold yellow]:wave: Exited successfully. Goodbye![/bold yellow]\n"))
            break
        elif choice in ["timeline", "last_timeline_liker"]:
            run_timeline_bot()
        elif choice in ["followers", "last_followers_liker"]:
            run_followers_bot()
        elif choice in ["posts", "last_post_liker"]:
            run_post_likers_bot()
        elif choice in ["comments", "last_comment_liker"]:
            run_comment_likers_bot()
        elif choice == "config":
            show_config_tree()
            questionary.text(em("\nPress [bold cyan]Enter[/bold cyan] to return to main menu..."), **kwargs).ask()


if __name__ == "__main__":
    main()
