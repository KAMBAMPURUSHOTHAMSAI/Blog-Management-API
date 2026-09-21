from datetime import datetime

from app.services.email_service import send_email


# =========================================================
# Activity Time Formatter
# =========================================================

def format_activity_time(
    activity_time: datetime,
) -> str:
    """
    Convert the activity timestamp into a
    simple, professional, human-readable format.
    """

    return activity_time.strftime(
        "%Y-%m-%d %I:%M %p"
    )


# =========================================================
# Comment Notification
# =========================================================

def send_comment_notification(
    owner_email: str,
    post_title: str,
    commenter_username: str,
    comment_text: str,
    activity_time: datetime,
) -> None:
    """
    Send an email notification to the post owner
    when another user comments on the post.
    """

    formatted_time = format_activity_time(
        activity_time
    )

    subject = (
        f"New comment on your post: "
        f"{post_title}"
    )

    body = (
        f"Hello,\n\n"
        f"Post: {post_title}\n"
        f"User: {commenter_username}\n"
        f"Activity: Commented on your post\n"
        f"Time: {formatted_time}\n\n"
        f"Comment:\n"
        f"{comment_text}\n\n"
        f"Blog Management API"
    )

    send_email(
        to_email=owner_email,
        subject=subject,
        body=body,
    )


# =========================================================
# Like Notification
# =========================================================

def send_like_notification(
    owner_email: str,
    post_title: str,
    liker_username: str,
    activity_time: datetime,
) -> None:
    """
    Send an email notification to the post owner
    when another user likes the post.
    """

    formatted_time = format_activity_time(
        activity_time
    )

    subject = (
        f"New like on your post: "
        f"{post_title}"
    )

    body = (
        f"Hello,\n\n"
        f"Post: {post_title}\n"
        f"User: {liker_username}\n"
        f"Activity: Liked your post\n"
        f"Time: {formatted_time}\n\n"
        f"Blog Management API"
    )

    send_email(
        to_email=owner_email,
        subject=subject,
        body=body,
    )