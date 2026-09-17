from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# Subscription Plan Model
# =========================================================

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Plan price
    price = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Number of posts allowed
    # None = Unlimited
    max_posts = Column(
        Integer,
        nullable=True,
    )

    # Number of images allowed per post
    # None = Unlimited
    max_images_per_post = Column(
        Integer,
        nullable=True,
    )

    # Number of likes allowed
    # None = Unlimited
    max_likes = Column(
        Integer,
        nullable=True,
    )

    # Number of comments allowed
    # None = Unlimited
    max_comments = Column(
        Integer,
        nullable=True,
    )

    # Subscription duration
    duration_days = Column(
        Integer,
        nullable=False,
        default=30,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # =====================================================
    # Relationships
    # =====================================================

    users = relationship(
        "User",
        back_populates="subscription_plan",
    )

    billing_history = relationship(
        "BillingHistory",
        back_populates="plan",
    )

    # =====================================================
    # Model-level subscription checks
    # =====================================================

    def can_create_post(self, current_post_count: int) -> bool:
        """
        Check whether the user can create another post.
        None means unlimited.
        """
        if self.max_posts is None:
            return True

        return current_post_count < self.max_posts

    def can_upload_images(self, image_count: int) -> bool:
        """
        Check whether the requested number of images
        is allowed for a post.
        """
        if self.max_images_per_post is None:
            return True

        return image_count <= self.max_images_per_post

    def can_like(self, current_like_count: int) -> bool:
        """
        Check whether the user can like another post.
        None means unlimited.
        """
        if self.max_likes is None:
            return True

        return current_like_count < self.max_likes

    def can_comment(self, current_comment_count: int) -> bool:
        """
        Check whether the user can add another comment.
        None means unlimited.
        """
        if self.max_comments is None:
            return True

        return current_comment_count < self.max_comments

    def is_unlimited(self) -> bool:
        """
        Returns True when all major limits are unlimited.
        """
        return (
            self.max_posts is None
            and self.max_images_per_post is None
            and self.max_likes is None
            and self.max_comments is None
        )


# =========================================================
# User Model
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password = Column(
        String(255),
        nullable=False,
    )

    # =====================================================
    # Active Subscription Information
    # =====================================================

    subscription_plan_id = Column(
        Integer,
        ForeignKey(
            "subscription_plans.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    subscription_start_date = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    subscription_end_date = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship with active subscription plan
    subscription_plan = relationship(
        "SubscriptionPlan",
        back_populates="users",
    )

    # =====================================================
    # Existing Relationships
    # =====================================================

    posts = relationship(
        "Post",
        back_populates="author",
        cascade="all, delete-orphan",
    )

    comments = relationship(
        "Comment",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    likes = relationship(
        "Like",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    billing_history = relationship(
        "BillingHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # =====================================================
    # Active Subscription Check
    # =====================================================

    def has_active_subscription(self) -> bool:
        """
        Check whether the user currently has an active
        subscription.

        SQLite may return datetime values without timezone
        information, so both current time and stored values
        are normalized to naive UTC.
        """

        if self.subscription_plan is None:
            return False

        if not self.subscription_plan.is_active:
            return False

        # Current UTC time without timezone information
        now = utc_now().replace(tzinfo=None)

        # Normalize stored datetime values
        start_date = self.subscription_start_date
        end_date = self.subscription_end_date

        if start_date is not None:
            start_date = start_date.replace(tzinfo=None)

        if end_date is not None:
            end_date = end_date.replace(tzinfo=None)

        # Check subscription start date
        if start_date is not None and now < start_date:
            return False

        # Check subscription end date
        if end_date is not None and now > end_date:
            return False

        return True

    def get_active_plan(self):
        """
        Return the user's active subscription plan.
        Returns None if the subscription is not active.
        """

        if self.has_active_subscription():
            return self.subscription_plan

        return None


# =========================================================
# Post Model
# =========================================================

class Post(Base):
    __tablename__ = "posts"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    content = Column(
        Text,
        nullable=False,
    )

    # Existing image field
    # Kept for backward compatibility
    image = Column(
        String(500),
        nullable=True,
    )

    author_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # =====================================================
    # Relationships
    # =====================================================

    author = relationship(
        "User",
        back_populates="posts",
    )

    comments = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    likes = relationship(
        "Like",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    # Multiple images
    post_images = relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImage.id",
    )

    # =====================================================
    # Return all images
    # =====================================================

    @property
    def images(self) -> list[str]:
        """
        Return all images belonging to this post.

        The old `image` field is returned first.
        Additional images come from the `post_images` table.
        """

        image_urls = []

        if self.image:
            image_urls.append(self.image)

        image_urls.extend(
            item.image_url
            for item in self.post_images
        )

        return image_urls


# =========================================================
# Post Image Model
# =========================================================

class PostImage(Base):
    __tablename__ = "post_images"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    post_id = Column(
        Integer,
        ForeignKey(
            "posts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    image_url = Column(
        String(500),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationship back to post
    post = relationship(
        "Post",
        back_populates="post_images",
    )


# =========================================================
# Comment Model
# =========================================================

class Comment(Base):
    __tablename__ = "comments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    post_id = Column(
        Integer,
        ForeignKey(
            "posts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    text = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    post = relationship(
        "Post",
        back_populates="comments",
    )

    user = relationship(
        "User",
        back_populates="comments",
    )


# =========================================================
# Like Model
# =========================================================

class Like(Base):
    __tablename__ = "likes"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    post_id = Column(
        Integer,
        ForeignKey(
            "posts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Prevent the same user from liking the same post twice
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "user_id",
            name="unique_post_user_like",
        ),
    )

    post = relationship(
        "Post",
        back_populates="likes",
    )

    user = relationship(
        "User",
        back_populates="likes",
    )


# =========================================================
# Billing History Model
# =========================================================

class BillingHistory(Base):
    __tablename__ = "billing_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # User who purchased/subscribed
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Subscription plan purchased
    plan_id = Column(
        Integer,
        ForeignKey(
            "subscription_plans.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Amount paid
    price = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Subscription validity
    start_date = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_date = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Fake/sample transaction ID
    transaction_id = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # Generated invoice PDF path
    invoice_path = Column(
        String(500),
        nullable=True,
    )

    # Billing status
    status = Column(
        String(30),
        nullable=False,
        default="completed",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # =====================================================
    # Relationships
    # =====================================================

    user = relationship(
        "User",
        back_populates="billing_history",
    )

    plan = relationship(
        "SubscriptionPlan",
        back_populates="billing_history",
    )