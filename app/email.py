import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings


logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
) -> None:
    """
    Send an email using the configured SMTP server.

    If SMTP settings are not configured, the function skips
    sending instead of breaking the API request.
    """

    # Skip email sending when SMTP is not configured.
    if not (
        settings.SMTP_HOST
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and settings.EMAIL_FROM
    ):
        logger.warning(
            "SMTP is not configured. Email notification skipped."
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
        ) as server:
            server.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
            )

            server.send_message(message)

        logger.info(
            "Email sent successfully to %s",
            to_email,
        )

    except Exception:
        logger.exception(
            "Failed to send email to %s",
            to_email,
        )


def send_comment_notification(
    owner_email: str,
    post_title: str,
    commenter_username: str,
    comment_text: str,
) -> None:
    """
    Notify a post owner when someone comments on their post.
    """

    subject = f"New comment on your post: {post_title}"

    body = (
        f"Hello,\n\n"
        f"{commenter_username} commented on your post "
        f"'{post_title}'.\n\n"
        f"Comment:\n"
        f"{comment_text}\n\n"
        f"Blog Management API"
    )

    send_email(
        to_email=owner_email,
        subject=subject,
        body=body,
    )


def send_like_notification(
    owner_email: str,
    post_title: str,
    liker_username: str,
) -> None:
    """
    Notify a post owner when someone likes their post.
    """

    subject = f"New like on your post: {post_title}"

    body = (
        f"Hello,\n\n"
        f"{liker_username} liked your post "
        f"'{post_title}'.\n\n"
        f"Blog Management API"
    )

    send_email(
        to_email=owner_email,
        subject=subject,
        body=body,
    )