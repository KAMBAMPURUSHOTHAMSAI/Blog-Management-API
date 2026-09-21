from datetime import datetime, timezone

from app.services.email_service import send_email
from app.services.notification_service import (
    send_comment_notification as _send_comment_notification,
    send_like_notification as _send_like_notification,
)


# =========================================================
# Backward-Compatible Comment Notification
# =========================================================

def send_comment_notification(
    owner_email: str,
    post_title: str,
    commenter_username: str,
    comment_text: str,
    activity_time: datetime | None = None,
) -> None:
    """
    Backward-compatible wrapper for comment notifications.

    Existing code can continue calling this function with
    the old four arguments. New code can provide the exact
    activity timestamp.
    """

    if activity_time is None:
        activity_time = datetime.now(
            timezone.utc
        )

    _send_comment_notification(
        owner_email=owner_email,
        post_title=post_title,
        commenter_username=commenter_username,
        comment_text=comment_text,
        activity_time=activity_time,
    )


# =========================================================
# Backward-Compatible Like Notification
# =========================================================

def send_like_notification(
    owner_email: str,
    post_title: str,
    liker_username: str,
    activity_time: datetime | None = None,
) -> None:
    """
    Backward-compatible wrapper for like notifications.

    Existing code can continue calling this function with
    the old three arguments. New code can provide the exact
    activity timestamp.
    """

    if activity_time is None:
        activity_time = datetime.now(
            timezone.utc
        )

    _send_like_notification(
        owner_email=owner_email,
        post_title=post_title,
        liker_username=liker_username,
        activity_time=activity_time,
    )


# =========================================================
# Public Email Sender
# =========================================================

__all__ = [
    "send_email",
    "send_comment_notification",
    "send_like_notification",
]