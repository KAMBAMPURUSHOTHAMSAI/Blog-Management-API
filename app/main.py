from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import models
from app.database import Base, engine
from app.routers import (
    auth,
    comments,
    dashboard,
    likes,
    posts,
    subscriptions,
)


# ============================================================
# Create Required Media Directories
# ============================================================

Path("media").mkdir(
    parents=True,
    exist_ok=True,
)

Path("media/posts").mkdir(
    parents=True,
    exist_ok=True,
)

Path("media/invoices").mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Create Database Tables
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# Create Default Subscription Plans
# ============================================================

def create_default_subscription_plans():
    """
    Create Basic, Premium and Pro plans if they
    do not already exist.

    This function is safe to run multiple times.
    Existing plans will not be duplicated.
    """

    with Session(engine) as db:

        plans = [
            {
                "name": "Basic",
                "price": 0.0,
                "max_posts": 1,
                "max_images_per_post": 1,
                "max_likes": 5,
                "max_comments": 5,
                "duration_days": 30,
            },
            {
                "name": "Premium",
                "price": 199.0,
                "max_posts": 2,
                "max_images_per_post": 2,
                "max_likes": 20,
                "max_comments": 20,
                "duration_days": 30,
            },
            {
                "name": "Pro",
                "price": 399.0,
                "max_posts": None,
                "max_images_per_post": None,
                "max_likes": None,
                "max_comments": None,
                "duration_days": 30,
            },
        ]

        for plan_data in plans:

            existing_plan = (
                db.query(
                    models.SubscriptionPlan
                )
                .filter(
                    models.SubscriptionPlan.name
                    == plan_data["name"]
                )
                .first()
            )

            if existing_plan is None:

                new_plan = models.SubscriptionPlan(
                    name=plan_data["name"],
                    price=plan_data["price"],
                    max_posts=plan_data["max_posts"],
                    max_images_per_post=plan_data[
                        "max_images_per_post"
                    ],
                    max_likes=plan_data[
                        "max_likes"
                    ],
                    max_comments=plan_data[
                        "max_comments"
                    ],
                    duration_days=plan_data[
                        "duration_days"
                    ],
                    is_active=True,
                )

                db.add(new_plan)

        db.commit()


# ============================================================
# Initialize Default Plans
# ============================================================

create_default_subscription_plans()


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Blog Management API",
    description=(
        "A mini blogging system with JWT authentication, "
        "posts, comments, likes, email notifications, "
        "image uploads, search, pagination, "
        "subscription-based access control, "
        "and user dashboard analytics."
    ),
    version="2.0.0",
)


# ============================================================
# Serve Uploaded Media Files
# ============================================================

app.mount(
    "/media",
    StaticFiles(directory="media"),
    name="media",
)


# ============================================================
# Include Routers
# ============================================================

app.include_router(
    auth.router
)

app.include_router(
    posts.router
)

app.include_router(
    comments.router
)

app.include_router(
    likes.router
)

app.include_router(
    subscriptions.router
)

app.include_router(
    dashboard.router
)


# ============================================================
# Health Check
# ============================================================

@app.get(
    "/",
    tags=["Health"],
)
def root():
    return {
        "message": "Blog Management API is running"
    }