from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
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


# =========================
# User Model
# =========================

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


# =========================
# Post Model
# =========================

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

    # Stores the uploaded image path/URL
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


# =========================
# Comment Model
# =========================

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


# =========================
# Like Model
# =========================

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