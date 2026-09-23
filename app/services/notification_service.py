from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Notification
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
# In-App Notification Creator
# =========================================================

def create_in_app_notification(
    db: Session,
    user_id: int,
    message: str,
    notification_type: str,
) -> Notification:
    """
    Create an in-app notification for a user.

    This function only adds the notification to the
    current database transaction.

    The caller is responsible for db.commit().
    """

    notification = Notification(
        user_id=user_id,
        message=message,
        notification_type=notification_type,
        is_read=False,
    )

    db.add(notification)

    return notification


# =========================================================
# Like - In-App Notification
# =========================================================

def create_like_notification(
    db: Session,
    owner_user_id: int,
    post_title: str,
    liker_username: str,
) -> Notification:
    """
    Create an in-app notification when a user likes
    another user's post.
    """

    message = (
        f"{liker_username} liked your post: "
        f"{post_title}"
    )

    return create_in_app_notification(
        db=db,
        user_id=owner_user_id,
        message=message,
        notification_type="like",
    )


# =========================================================
# Comment - In-App Notification
# =========================================================

def create_comment_notification(
    db: Session,
    owner_user_id: int,
    post_title: str,
    commenter_username: str,
) -> Notification:
    """
    Create an in-app notification when a user comments
    on another user's post.
    """

    message = (
        f"{commenter_username} commented on your post: "
        f"{post_title}"
    )

    return create_in_app_notification(
        db=db,
        user_id=owner_user_id,
        message=message,
        notification_type="comment",
    )


# =========================================================
# Subscription - In-App Notification
# =========================================================

def create_subscription_notification(
    db: Session,
    user_id: int,
    plan_name: str,
    action: str = "activated",
) -> Notification:
    """
    Create an in-app notification when a subscription
    is activated or renewed.
    """

    if action == "renewed":
        message = (
            f"Your {plan_name} subscription "
            f"has been renewed successfully."
        )
    else:
        message = (
            f"Your {plan_name} subscription "
            f"has been activated successfully."
        )

    return create_in_app_notification(
        db=db,
        user_id=user_id,
        message=message,
        notification_type="subscription",
    )


# =========================================================
# Comment - Email Notification
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
# Like - Email Notification
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