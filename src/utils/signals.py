import signal
import sys
from src.utils.console import log_warning, log_error, console, fix_persian

_shutdown_registered = False

def register_graceful_shutdown(on_shutdown=None):
    """Registers clean signal handlers for Ctrl+C (SIGINT) and SIGTERM."""
    global _shutdown_registered
    if _shutdown_registered:
        return
    _shutdown_registered = True

    def _sig_handler(sig, frame):
        log_warning("\n:hand: Process interrupted by user (SIGINT/Ctrl+C). Performing graceful shutdown...")
        try:
            if callable(on_shutdown):
                on_shutdown()
        except Exception as e:
            log_error(f"Error during shutdown callback: {e}")
        console.print(f"[bold green]:white_check_mark: {fix_persian('توقف ایمن انجام شد و داده‌ها در پایگاه داده پایدار ذخیره گردید.')}[/bold green]")
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass
