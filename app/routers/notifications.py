from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Notification, User
from app.schemas import (
    NotificationResponse,
    NotificationUnreadCountResponse,
)


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


# =========================================================
# Get Current User Notifications
# =========================================================

@router.get(
    "/",
    response_model=list[NotificationResponse],
    summary="Get current user's notifications",
)
def get_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return recent notifications belonging only to
    the authenticated user.

    Newest notifications are returned first.
    """

    # -----------------------------------------------------
    # Validate limit
    # -----------------------------------------------------

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    # -----------------------------------------------------
    # Fetch current user's notifications
    # -----------------------------------------------------

    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id
        )
        .order_by(
            Notification.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    return notifications


# =========================================================
# Get Unread Notification Count
# =========================================================

@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
    summary="Get unread notification count",
)
def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the number of unread notifications
    belonging to the authenticated user.
    """

    unread_count = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )

    return {
        "unread_count": unread_count
    }


# =========================================================
# Mark One Notification as Read
# =========================================================

@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark one notification as read.

    A user can only update their own notification.
    """

    notification = (
        db.query(Notification)
        .filter(
            Notification.id
            == notification_id,
            Notification.user_id
            == current_user.id,
        )
        .first()
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return notification


# =========================================================
# Mark One Notification as Unread
# =========================================================

@router.patch(
    "/{notification_id}/unread",
    response_model=NotificationResponse,
    summary="Mark a notification as unread",
)
def mark_notification_as_unread(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark one notification as unread.

    A user can only update their own notification.
    """

    notification = (
        db.query(Notification)
        .filter(
            Notification.id
            == notification_id,
            Notification.user_id
            == current_user.id,
        )
        .first()
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = False

    db.commit()
    db.refresh(notification)

    return notification


# =========================================================
# Mark All Notifications as Read
# =========================================================

@router.patch(
    "/read-all",
    summary="Mark all current user's notifications as read",
)
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all unread notifications belonging to the
    authenticated user as read.
    """

    updated_count = (
        db.query(Notification)
        .filter(
            Notification.user_id
            == current_user.id,
            Notification.is_read.is_(False),
        )
        .update(
            {
                Notification.is_read: True
            },
            synchronize_session=False,
        )
    )

    db.commit()

    return {
        "message": (
            "All notifications marked as read"
        ),
        "updated_count": updated_count,
    }