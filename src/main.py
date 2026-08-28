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

    show_banner("Instagram Bot Hub", "Select bot mode to run & automate your Instagram actions")

    choice = questionary.select(
        "Select bot mode to run:\n  ↪ " + fix_persian("انتخاب ربات برای اجرا:"),
        choices=[
            questionary.Choice(
                title=f":newspaper: 1. Timeline Feed Liker (Continuous Feed Liker with Auto-Refresh)\n   ↪ {fix_persian('لایک مداوم پست‌های فید تایم‌لاین با رفرش خودکار')}",
                value="timeline"
            ),
            questionary.Choice(
                title=f":busts_in_silhouette: 2. Following Feed Liker (Automated Liker for Accounts You Follow)\n   ↪ {fix_persian('لایک خودکار جدیدترین پست‌های فالووینگ‌ها')}",
                value="followers"
            ),
            questionary.Choice(
                title=f":target: 3. Post Likers Bot (Extract Likers & Automated Engagement)\n   ↪ {fix_persian('استخراج و تعامل با لایک‌کنندگان پست هدف')}",
                value="posts"
            ),
            questionary.Choice(
                title=f":door: 4. Exit\n   ↪ {fix_persian('خروج از برنامه')}",
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
        console.print(f"\n[bold yellow]:wave: {fix_persian('با موفقیت خارج شدید.')} Goodbye![/bold yellow]\n")

if __name__ == "__main__":
    main()
