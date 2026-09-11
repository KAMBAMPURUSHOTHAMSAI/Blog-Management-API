from fastapi import FastAPI

from app import models
from app.database import Base, engine
from app.routers import auth, comments, likes, posts


# Create all database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Blog Management API",
    description=(
        "A mini blogging system with JWT authentication, "
        "posts, comments, likes, and email notifications."
    ),
    version="1.0.0",
)


# Include API routers
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(likes.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Blog Management API is running"
    }