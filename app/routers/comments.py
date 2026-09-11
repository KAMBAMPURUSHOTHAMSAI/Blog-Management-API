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

    # Create the comment
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