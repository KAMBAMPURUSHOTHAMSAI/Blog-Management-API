from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.email import send_like_notification
from app.models import Like, Post, User


router = APIRouter(
    prefix="/posts",
    tags=["Likes"],
)


# =========================
# Like Post
# =========================

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

    # Check whether this user already liked the post
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

    # Create like
    like = Like(
        post_id=post_id,
        user_id=current_user.id,
    )

    db.add(like)

    try:
        db.commit()
        db.refresh(like)
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already liked this post",
        )

    # Notify the post owner
    background_tasks.add_task(
        send_like_notification,
        post.author.email,
        post.title,
        current_user.username,
    )

    return {
        "message": "Post liked successfully"
    }


# =========================
# Unlike Post
# =========================

@router.delete(
    "/{post_id}/like",
)
def unlike_post(
    post_id: int,
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

    # Find the current user's like
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

    db.delete(like)
    db.commit()

    return {
        "message": "Post unliked successfully"
    }