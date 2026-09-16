from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =========================
# User Schemas
# =========================

class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
    )

    email: EmailStr

    password: str = Field(
        min_length=6,
        max_length=100,
    )


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================
# Authentication Schemas
# =========================

class LoginRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
    )

    password: str = Field(
        min_length=6,
        max_length=100,
    )


class Token(BaseModel):
    access_token: str
    token_type: str


# =========================
# Post Schemas
# =========================

class PostCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
    )

    content: str = Field(
        min_length=1,
        max_length=10000,
    )


class PostUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=10000,
    )


class PostResponse(BaseModel):
    id: int
    title: str
    content: str
    image: str | None = None
    author_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================
# Paginated Post Response
# =========================

class PaginatedPostsResponse(BaseModel):
    page: int
    limit: int
    total_count: int
    total_pages: int
    search: str | None = None
    posts: list[PostResponse]


# =========================
# Comment Schemas
# =========================

class CommentCreate(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=2000,
    )


class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    text: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )