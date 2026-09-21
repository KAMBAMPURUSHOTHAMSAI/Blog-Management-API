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

    This function is intended to be called through
    FastAPI BackgroundTasks, so email sending does not
    block the main API response.

    Any SMTP/configuration error is logged and does not
    interrupt the main application flow.
    """

    # =====================================================
    # Check SMTP Configuration
    # =====================================================

    if not (
        settings.SMTP_HOST
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and settings.EMAIL_FROM
    ):
        logger.warning(
            "SMTP is not configured. "
            "Email notification skipped."
        )
        return

    # =====================================================
    # Create Email Message
    # =====================================================

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email

    message.set_content(body)

    # =====================================================
    # Send Email
    # =====================================================

    try:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
        ) as server:

            server.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD,
            )

            server.send_message(
                message
            )

        logger.info(
            "Email sent successfully to %s",
            to_email,
        )

    except Exception:
        # Email failure must not break
        # the main blog functionality.
        logger.exception(
            "Failed to send email to %s",
            to_email,
        )