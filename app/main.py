from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models
from app.database import Base, engine
from app.routers import auth, comments, likes, posts


# ============================================================
# Create Database Tables
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Blog Management API",
    description=(
        "A mini blogging system with JWT authentication, "
        "posts, comments, likes, email notifications, "
        "image uploads, search, and pagination."
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

app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(likes.router)


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