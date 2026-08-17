import os
import sys

# Ensure workspace root is in sys.path when executed directly as `python src/main.py` or `uv run src/main.py`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import questionary
from src.bot.utils import show_banner, console, fix_persian
from src.bot.followers_liker import main as run_followers_bot
from src.bot.post_liker import main as run_post_likers_bot

def main():
    """Interactive CLI menu to select and launch bots."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower().strip()
        if arg in ["followers", "following", "1"]:
            run_followers_bot()
            return
        elif arg in ["post-likers", "likers", "post", "2"]:
            run_post_likers_bot()
            return

    show_banner("Instagram Automation Hub", "Interactive Multi-Bot Platform for Instagram Engagement")

    choice = questionary.select(
        "Select the bot you want to run:",
        choices=[
            questionary.Choice(f"👥 Following Engagement Bot ({fix_persian('لایک و کامنت هوشمند فالووینگ‌ها')})", value="followers"),
            questionary.Choice(f"🎯 Post Likers Bot ({fix_persian('استخراج و تعامل با لایک‌کننده‌های پست هدف')})", value="likers"),
            questionary.Choice(f"🚪 Exit ({fix_persian('خروج')})", value="exit"),
        ]
    ).ask()

    if choice == "followers":
        run_followers_bot()
    elif choice == "likers":
        run_post_likers_bot()
    else:
        console.print("[yellow]:wave: Exiting. Have a great day![/yellow]")
        sys.exit(0)

if __name__ == "__main__":
    main()
