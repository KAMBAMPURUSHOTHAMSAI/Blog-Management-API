from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Comment, Like, Post, User
from app.schemas import (
    DashboardPostStats,
    DashboardResponse,
)


router = APIRouter(
    prefix="/user",
    tags=["Dashboard"],
)


# =========================================================
# User Dashboard Statistics API
# =========================================================

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get current user's dashboard statistics",
)
def get_user_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return personalized dashboard statistics for the
    authenticated user.

    Statistics:
    - Total posts created
    - Total comments made
    - Total likes received on user's posts
    - Per-post likes and comments

    Post views are not included because view tracking
    is not currently enabled.
    """

    # =====================================================
    # Aggregate likes per post
    # =====================================================

    like_counts = (
        db.query(
            Like.post_id.label("post_id"),
            func.count(Like.id).label(
                "likes_received"
            ),
        )
        .group_by(
            Like.post_id
        )
        .subquery()
    )

    # =====================================================
    # Aggregate comments per post
    # =====================================================

    comment_counts = (
        db.query(
            Comment.post_id.label("post_id"),
            func.count(Comment.id).label(
                "comments_received"
            ),
        )
        .group_by(
            Comment.post_id
        )
        .subquery()
    )

    # =====================================================
    # Get current user's posts with statistics
    # =====================================================

    post_stats = (
        db.query(
            Post.id.label("post_id"),
            Post.title.label("title"),

            func.coalesce(
                like_counts.c.likes_received,
                0,
            ).label("likes_received"),

            func.coalesce(
                comment_counts.c.comments_received,
                0,
            ).label("comments_received"),
        )
        .outerjoin(
            like_counts,
            like_counts.c.post_id == Post.id,
        )
        .outerjoin(
            comment_counts,
            comment_counts.c.post_id == Post.id,
        )
        .filter(
            Post.author_id == current_user.id
        )
        .order_by(
            Post.created_at.desc()
        )
        .all()
    )

    # =====================================================
    # Total comments made by current user
    # =====================================================

    total_comments = (
        db.query(Comment)
        .filter(
            Comment.user_id == current_user.id
        )
        .count()
    )

    # =====================================================
    # Build post statistics
    # =====================================================

    posts = []

    total_likes_received = 0

    for post in post_stats:

        likes_received = int(
            post.likes_received or 0
        )

        comments_received = int(
            post.comments_received or 0
        )

        total_likes_received += (
            likes_received
        )

        posts.append(
            DashboardPostStats(
                post_id=post.post_id,
                title=post.title,
                likes_received=likes_received,
                comments_received=comments_received,
            )
        )

    # =====================================================
    # Total posts
    # =====================================================

    total_posts = len(posts)

    # =====================================================
    # Dashboard response
    # =====================================================

    return DashboardResponse(
        user_id=current_user.id,
        username=current_user.username,
        total_posts=total_posts,
        total_comments=total_comments,
        total_likes_received=total_likes_received,
        total_post_views=None,
        posts=posts,
    )


# =========================================================
# Dashboard Web Page
# =========================================================

@router.get(
    "/dashboard/page",
    include_in_schema=False,
)
def dashboard_page():
    """
    Serve the dashboard HTML page.
    """

    dashboard_file = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "dashboard.html"
    )

    if not dashboard_file.exists():
        raise FileNotFoundError(
            f"Dashboard file not found: {dashboard_file}"
        )

    return FileResponse(
        path=dashboard_file,
        media_type="text/html",
    )