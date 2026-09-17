from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.email import send_comment_notification
from app.models import Comment, Post, User
from app.schemas import CommentCreate, CommentResponse


router = APIRouter(
    prefix="/posts",
    tags=["Comments"],
)


# =========================
# Add Comment
# =========================

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
    # Check whether the post exists
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

    # =========================
    # Subscription Plan Check
    # =========================

    plan = current_user.get_active_plan()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have an active subscription.",
        )

    # Count current user's comments
    current_comment_count = (
        db.query(Comment)
        .filter(
            Comment.user_id == current_user.id
        )
        .count()
    )

    # Check plan limit
    if not plan.can_comment(current_comment_count):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You’ve reached your plan limit. Kindly upgrade your plan to continue.",
        )

    # =========================
    # Create Comment
    # =========================

    comment = Comment(
        post_id=post.id,
        user_id=current_user.id,
        text=comment_data.text,
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Send notification to post owner in the background
    background_tasks.add_task(
        send_comment_notification,
        post.author.email,
        post.title,
        current_user.username,
        comment.text,
    )

    return comment


# =========================
# Get Comments - Public
# =========================

@router.get(
    "/{post_id}/comments",
    response_model=list[CommentResponse],
)
def get_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    # Check whether the post exists
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

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    return comments