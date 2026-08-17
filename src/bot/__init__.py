"""Instagram Bot core package."""
from src.bot.bot import Bot
from src.bot.followers_liker import main as run_followers_bot
from src.bot.post_liker import main as run_post_likers_bot

__all__ = ["Bot", "run_followers_bot", "run_post_likers_bot"]
