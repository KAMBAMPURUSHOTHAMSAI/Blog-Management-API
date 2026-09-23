from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Comment, Post, User
from app.schemas import CommentCreate, CommentResponse
from app.services.notification_service import (
    create_comment_notification,
    send_comment_notification,
)


router = APIRouter(
    prefix="/posts",
    tags=["Comments"],
)


# =========================================================
# Add Comment
# =========================================================

@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: int,
    comment_data: CommentCreate,
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
    # Count Current User's Comments
    # =====================================================

    current_comment_count = (
        db.query(Comment)
        .filter(
            Comment.user_id == current_user.id
        )
        .count()
    )

    # =====================================================
    # Check Plan Limit
    # =====================================================

    if not plan.can_comment(
        current_comment_count
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You’ve reached your plan limit. "
                "Kindly upgrade your plan to continue."
            ),
        )

    # =====================================================
    # Create Comment
    # =====================================================

    comment = Comment(
        post_id=post.id,
        user_id=current_user.id,
        text=comment_data.text,
    )

    db.add(comment)

    # =====================================================
    # Create In-App Notification
    # =====================================================
    #
    # The notification is added to the same database
    # transaction as the comment.
    #
    # No commit happens inside the helper function.
    # =====================================================

    create_comment_notification(
        db=db,
        owner_user_id=post.author_id,
        post_title=post.title,
        commenter_username=current_user.username,
    )

    # =====================================================
    # Commit Comment + In-App Notification
    # =====================================================

    db.commit()

    db.refresh(comment)

    # =====================================================
    # Send Comment Email Notification
    # =====================================================
    #
    # Email is still handled in the background.
    # This keeps the API response fast.
    # =====================================================

    background_tasks.add_task(
        send_comment_notification,
        post.author.email,
        post.title,
        current_user.username,
        comment.text,
        comment.created_at,
    )

    return comment


# =========================================================
# Get Comments - Public
# =========================================================

@router.get(
    "/{post_id}/comments",
    response_model=list[CommentResponse],
)
def get_comments(
    post_id: int,
    db: Session = Depends(get_db),
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
    # Get Comments
    # =====================================================

    comments = (
        db.query(Comment)
        .filter(
            Comment.post_id == post_id
        )
        .order_by(
            Comment.created_at.asc()
        )
        .all()
    )

    return comments