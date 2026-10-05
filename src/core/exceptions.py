"""
Robust Exception Mapping for Instagrapi.
Safely extracts or provides fallback exception classes across various instagrapi releases.
"""
import instagrapi.exceptions as ie

# Base instagrapi exception
ClientError = getattr(ie, "ClientError", Exception)

def _get_exc(name: str, base=ClientError):
    """Safely retrieves exception class from instagrapi.exceptions or returns a custom subclass."""
    if hasattr(ie, name):
        return getattr(ie, name)
    # Create a dynamic fallback exception class if not present in installed version
    return type(name, (base,), {})

# Common Authentication & Session Exceptions
LoginRequired = _get_exc("LoginRequired")
ClientLoginRequired = _get_exc("ClientLoginRequired", LoginRequired)
TwoFactorRequired = _get_exc("TwoFactorRequired")
BadPassword = _get_exc("BadPassword")
InvalidUsername = _get_exc("InvalidUsername")
AccountDisabled = _get_exc("AccountDisabled")
ChallengeRequired = _get_exc("ChallengeRequired")
ChallengeUnknownStep = _get_exc("ChallengeUnknownStep")

# Rate Limit & Action Blocks
FeedbackRequired = _get_exc("FeedbackRequired")
PleaseWaitFewMinutes = _get_exc("PleaseWaitFewMinutes")
RateLimitError = _get_exc("RateLimitError")

# Media & User Exceptions
MediaNotFound = _get_exc("MediaNotFound")
UserNotFound = _get_exc("UserNotFound")
PrivateAccount = _get_exc("PrivateAccount")

# HTTP & Network Exceptions
ClientConnectionError = _get_exc("ClientConnectionError")
ClientBadRequestError = _get_exc("ClientBadRequestError")
ClientForbiddenError = _get_exc("ClientForbiddenError")
ClientThrottledError = _get_exc("ClientThrottledError")
ClientNotFoundError = _get_exc("ClientNotFoundError")
ClientJSONDecodeError = _get_exc("ClientJSONDecodeError")
ProxyAddressIsBlocked = _get_exc("ProxyAddressIsBlocked")

def is_network_error(exc: Exception) -> bool:
    """Detects if an exception is caused by DNS resolution failure, connection drop, timeout, or proxy error."""
    if not isinstance(exc, Exception):
        return False
    exc_name = exc.__class__.__name__.lower()
    exc_str = str(exc).lower()
    keywords = [
        "dns", "resolve", "connection", "connect", "timeout", "proxy",
        "ssl", "transport", "network", "unreachable", "handshake"
    ]
    return any(k in exc_name or k in exc_str for k in keywords)
