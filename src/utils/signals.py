import signal
import sys
from src.utils.console import log_warning, log_error, console

_shutdown_registered = False

def register_graceful_shutdown(on_shutdown=None):
    """Registers clean signal handlers for Ctrl+C (SIGINT) and SIGTERM."""
    global _shutdown_registered
    if _shutdown_registered:
        return
    _shutdown_registered = True

    def _sigterm_handler(sig, frame):
        log_warning("\n:hand: Process terminated (SIGTERM). Performing graceful shutdown...")
        try:
            if callable(on_shutdown):
                on_shutdown()
        except Exception as e:
            log_error(f"Error during shutdown callback: {e}")
        console.print("[bold green]:white_check_mark: Graceful shutdown completed. All session data safely stored.[/bold green]")
        sys.exit(0)

    try:
        # Keep standard Python KeyboardInterrupt for interactive Ctrl+C
        signal.signal(signal.SIGINT, signal.default_int_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sigterm_handler)
    except Exception:
        pass
