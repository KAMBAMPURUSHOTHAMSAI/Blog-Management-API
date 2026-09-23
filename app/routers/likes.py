from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Like, Post, User
from app.services.notification_service import (
    create_like_notification,
    send_like_notification,
)


router = APIRouter(
    prefix="/posts",
    tags=["Likes"],
)


# =========================================================
# Like Post
# =========================================================

@router.post(
    "/{post_id}/like",
    status_code=status.HTTP_201_CREATED,
)
def like_post(
    post_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # =====================================================
    # Check whether the post exists
    # =====================================================

    post = (
        db.query(Post)
        .filter(Post.id == post_id)
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # =====================================================
    # Check whether this user already liked the post
    # =====================================================

    existing_like = (
        db.query(Like)
        .filter(
            Like.post_id == post_id,
            Like.user_id == current_user.id,
        )
        .first()
    )

    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already liked this post",
        )

    # =====================================================
    # Subscription Plan Check
    # =====================================================

    plan = current_user.get_active_plan()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have an active subscription."
            ),
        )

    # =====================================================
    # Count Current User's Active Likes
    # =====================================================

    current_like_count = (
        db.query(Like)
        .filter(
            Like.user_id == current_user.id
        )
        .count()
    )

    # =====================================================
    # Check Plan Limit
    # =====================================================

    if not plan.can_like(
        current_like_count
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You’ve reached your plan limit. "
                "Kindly upgrade your plan to continue."
            ),
        )

    # =====================================================
    # Capture Like Activity Timestamp
    # =====================================================

    activity_time = datetime.now(
        timezone.utc
    )

    # =====================================================
    # Create Like
    # =====================================================

    like = Like(
        post_id=post_id,
        user_id=current_user.id,
    )

    db.add(like)

    # =====================================================
    # Create In-App Notification
    # =====================================================
    #
    # The notification is added to the same transaction
    # as the Like.
    # =====================================================

    create_like_notification(
        db=db,
        owner_user_id=post.author_id,
        post_title=post.title,
        liker_username=current_user.username,
    )

    # =====================================================
    # Commit Like + In-App Notification
    # =====================================================

    try:
        db.commit()
        db.refresh(like)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already liked this post",
        )

    # =====================================================
    # Send Like Email Notification in Background
    # =====================================================
    #
    # Email sending remains asynchronous so it does not
    # delay the API response.
    # =====================================================

    background_tasks.add_task(
        send_like_notification,
        post.author.email,
        post.title,
        current_user.username,
        activity_time,
    )

    return {
        "message": "Post liked successfully"
    }


# =========================================================
# Unlike Post
# =========================================================

@router.delete(
    "/{post_id}/like",
)
def unlike_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # =====================================================
    # Check whether the post exists
    # =====================================================

    post = (
        db.query(Post)
        .filter(Post.id == post_id)
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # =====================================================
    # Find the Current User's Like
    # =====================================================

    like = (
        db.query(Like)
        .filter(
            Like.post_id == post_id,
            Like.user_id == current_user.id,
        )
        .first()
    )

    if like is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not liked this post",
        )

    # =====================================================
    # Remove Like
    # =====================================================

    db.delete(like)

    db.commit()

    return {
        "message": "Post unliked successfully"
    }