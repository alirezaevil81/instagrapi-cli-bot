import os
import sys

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import questionary
from src.database.engine import init_db
from src.utils.console import show_banner, console, fix_persian
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

    show_banner("Instagram Bot Hub", "Select bot mode to run")

    choice = questionary.select(
        "Which bot would you like to run?",
        choices=[
            questionary.Choice(
                title=f"1. {fix_persian('لایک مداوم پست‌های ۲۴ ساعت اخیر فید تایم‌لاین با رفرش خودکار')} (Timeline Feed 24h Liker)",
                value="timeline"
            ),
            questionary.Choice(
                title=f"2. {fix_persian('لایک خودکار پست‌های فالووینگ‌ها')} (Followers / Following Liker)",
                value="followers"
            ),
            questionary.Choice(
                title=f"3. {fix_persian('استخراج و تعامل با لایک‌کنندگان پست هدف')} (Post Likers Bot)",
                value="posts"
            ),
            questionary.Choice(
                title=f"4. {fix_persian('خروج')} (Exit)",
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
        console.print(f"[bold yellow]:wave: {fix_persian('با موفقیت خارج شدید.')} Goodbye![/bold yellow]")

if __name__ == "__main__":
    main()
