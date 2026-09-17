from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =========================================================
# User Schemas
# =========================================================

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


# =========================================================
# Authentication Schemas
# =========================================================

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


# =========================================================
# Post Schemas
# =========================================================

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
    images: list[str] = Field(
        default_factory=list
    )
    author_id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# Paginated Post Response
# =========================================================

class PaginatedPostsResponse(BaseModel):
    page: int
    limit: int
    total_count: int
    total_pages: int
    search: str | None = None
    posts: list[PostResponse]


# =========================================================
# Comment Schemas
# =========================================================

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


# =========================================================
# Subscription Plan Schemas
# =========================================================

class SubscriptionPlanResponse(BaseModel):
    id: int
    name: str
    price: float

    # None means unlimited
    max_posts: int | None
    max_images_per_post: int | None
    max_likes: int | None
    max_comments: int | None

    duration_days: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# Subscribe Request Schema
# =========================================================

class SubscribeRequest(BaseModel):
    plan_id: int = Field(
        gt=0,
        description="ID of the subscription plan",
    )


# =========================================================
# Billing History Response
# =========================================================

class BillingHistoryResponse(BaseModel):
    id: int

    user_id: int
    plan_id: int | None

    price: float

    start_date: datetime
    end_date: datetime

    transaction_id: str

    invoice_path: str | None = None

    status: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# Subscription Response
# =========================================================

class SubscriptionResponse(BaseModel):
    message: str

    user_id: int
    plan: SubscriptionPlanResponse

    subscription_start_date: datetime | None
    subscription_end_date: datetime | None

    billing: BillingHistoryResponse | None = None