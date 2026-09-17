import math
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import WithJsonSchema
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Post, PostImage, User
from app.schemas import (
    PaginatedPostsResponse,
    PostResponse,
)

router = APIRouter(
    prefix="/posts",
    tags=["Posts"],
)


# =========================================================
# Swagger UploadFile Fix
# =========================================================
# Newer FastAPI versions can generate
# contentMediaType instead of format=binary.
# Swagger UI may not show the file picker correctly
# for an array of UploadFile.
#
# This forces the OpenAPI schema to use:
# type: string
# format: binary
# =========================================================

SwaggerUploadFile = Annotated[
    UploadFile,
    WithJsonSchema(
        {
            "type": "string",
            "format": "binary",
        }
    ),
]


# =========================================================
# Media Configuration
# =========================================================

MEDIA_ROOT = Path("media")

POSTS_MEDIA_DIR = (
    MEDIA_ROOT / "posts"
)

POSTS_MEDIA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
}

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024


# =========================================================
# Subscription Limit Message
# =========================================================

PLAN_LIMIT_MESSAGE = (
    "You’ve reached your plan limit. "
    "Kindly upgrade your plan to continue."
)


# =========================================================
# Subscription Helper
# =========================================================

def get_active_subscription_plan(
    current_user: User,
):
    """
    Return the user's active subscription plan.
    """

    plan = current_user.get_active_plan()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have an active subscription. "
                "Please subscribe to a plan to continue."
            ),
        )

    return plan


# =========================================================
# Post Creation Limit
# =========================================================

def check_post_creation_limit(
    current_user: User,
    db: Session,
):
    """
    Check whether the user can create another post.
    """

    plan = get_active_subscription_plan(
        current_user
    )

    current_post_count = (
        db.query(Post)
        .filter(
            Post.author_id == current_user.id
        )
        .count()
    )

    if not plan.can_create_post(
        current_post_count
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PLAN_LIMIT_MESSAGE,
        )

    return plan


# =========================================================
# Save One Image
# =========================================================

def save_uploaded_image(
    image: UploadFile,
) -> str:
    """
    Validate and save one uploaded image.

    Returns:
        /media/posts/<filename>
    """

    if not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Image filename is missing",
        )

    extension = Path(
        image.filename
    ).suffix.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported image format. "
                "Allowed formats: JPG, JPEG, PNG, GIF, WEBP"
            ),
        )

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a valid image",
        )

    file_data = image.file.read()

    if not file_data:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty",
        )

    if len(file_data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image size must be 5 MB or less",
        )

    unique_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    file_path = (
        POSTS_MEDIA_DIR / unique_filename
    )

    with open(
        file_path,
        "wb",
    ) as buffer:
        buffer.write(file_data)

    return (
        f"/media/posts/{unique_filename}"
    )


# =========================================================
# Save Multiple Images
# =========================================================

def save_uploaded_images(
    images: list[UploadFile],
) -> list[str]:
    """
    Save multiple images.

    Returns:
        List of image URLs.
    """

    saved_images = []

    try:
        for image in images:

            image_url = save_uploaded_image(
                image
            )

            saved_images.append(
                image_url
            )

        return saved_images

    except Exception:

        # Delete files already saved
        # if another file fails.
        for image_url in saved_images:

            delete_image_file(
                image_url
            )

        raise


# =========================================================
# Delete Image File
# =========================================================

def delete_image_file(
    image_url: str | None,
) -> None:
    """
    Delete one image file from disk.
    """

    if not image_url:
        return

    filename = Path(
        image_url
    ).name

    if not filename:
        return

    file_path = (
        POSTS_MEDIA_DIR / filename
    )

    if file_path.exists():
        file_path.unlink()


# =========================================================
# Get All Existing Image URLs
# =========================================================

def get_post_image_urls(
    post: Post,
) -> list[str]:
    """
    Return all image URLs currently belonging
    to the post.
    """

    image_urls = []

    if post.image:
        image_urls.append(
            post.image
        )

    for post_image in (
        post.post_images
    ):
        image_urls.append(
            post_image.image_url
        )

    return image_urls


# =========================================================
# CREATE POST
# =========================================================

@router.post(
    "/create",
    response_model=PostResponse,
    status_code=201,
    summary="Create a new post with multiple images",
)
def create_post(
    title: str = Form(
        ...,
        min_length=1,
        max_length=200,
    ),

    content: str = Form(
        ...,
        min_length=1,
        max_length=10000,
    ),

    # Multiple file upload
    images: list[SwaggerUploadFile] = File(
        default=[],
        description=(
            "Upload one or multiple images "
            "according to your subscription plan."
        ),
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # Check post limit
    # -----------------------------------------------------

    plan = check_post_creation_limit(
        current_user=current_user,
        db=db,
    )

    # -----------------------------------------------------
    # Count requested images
    # -----------------------------------------------------

    image_count = len(images)

    # -----------------------------------------------------
    # Check image limit
    # -----------------------------------------------------

    if not plan.can_upload_images(
        image_count
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PLAN_LIMIT_MESSAGE,
        )

    # -----------------------------------------------------
    # Save images
    # -----------------------------------------------------

    saved_image_urls = []

    if images:

        saved_image_urls = (
            save_uploaded_images(
                images
            )
        )

    try:

        # -------------------------------------------------
        # Create Post
        # -------------------------------------------------

        post = Post(
            title=title.strip(),
            content=content.strip(),
            author_id=current_user.id,
        )

        # -------------------------------------------------
        # First image goes to old `image` column
        # -------------------------------------------------

        if saved_image_urls:

            post.image = (
                saved_image_urls[0]
            )

        db.add(post)

        # Get post ID
        db.flush()

        # -------------------------------------------------
        # Additional images
        # -------------------------------------------------

        for image_url in (
            saved_image_urls[1:]
        ):

            post_image = PostImage(
                post_id=post.id,
                image_url=image_url,
            )

            db.add(
                post_image
            )

        db.commit()

        db.refresh(post)

        return post

    except Exception:

        db.rollback()

        # Remove uploaded files
        # if database operation fails.
        for image_url in (
            saved_image_urls
        ):

            delete_image_file(
                image_url
            )

        raise


# =========================================================
# GET POSTS
# =========================================================

@router.get(
    "",
    response_model=PaginatedPostsResponse,
    summary="Get posts with search and pagination",
)
def get_posts(
    page: int = 1,
    limit: int = 10,
    search: str | None = None,

    db: Session = Depends(get_db),
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Page must be greater than "
                "or equal to 1"
            ),
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail=(
                "Limit must be between "
                "1 and 100"
            ),
        )

    query = db.query(Post)

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    if search and search.strip():

        search_value = (
            f"%{search.strip()}%"
        )

        query = query.filter(
            or_(
                Post.title.ilike(
                    search_value
                ),
                Post.content.ilike(
                    search_value
                ),
            )
        )

    # -----------------------------------------------------
    # Pagination
    # -----------------------------------------------------

    total_count = query.count()

    total_pages = (
        math.ceil(
            total_count / limit
        )
        if total_count > 0
        else 0
    )

    offset = (
        (page - 1) * limit
    )

    posts = (
        query
        .order_by(
            Post.created_at.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "page": page,
        "limit": limit,
        "total_count": total_count,
        "total_pages": total_pages,
        "search": search,
        "posts": posts,
    }


# =========================================================
# GET MY POSTS
# =========================================================

@router.get(
    "/mine",
    response_model=list[PostResponse],
    summary="Get current user's posts",
)
def get_my_posts(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    posts = (
        db.query(Post)
        .filter(
            Post.author_id
            == current_user.id
        )
        .order_by(
            Post.created_at.desc()
        )
        .all()
    )

    return posts


# =========================================================
# GET SINGLE POST
# =========================================================

@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Get a single post",
)
def get_post(
    post_id: int,

    db: Session = Depends(get_db),
):
    post = (
        db.query(Post)
        .filter(
            Post.id == post_id
        )
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    return post


# =========================================================
# UPDATE POST
# =========================================================

@router.put(
    "/{post_id}/update",
    response_model=PostResponse,
    summary="Update a post and optionally replace images",
)
def update_post(
    post_id: int,

    title: str | None = Form(
        default=None,
        min_length=1,
        max_length=200,
    ),

    content: str | None = Form(
        default=None,
        min_length=1,
        max_length=10000,
    ),

    images: list[SwaggerUploadFile] = File(
        default=[],
        description=(
            "Upload images to replace "
            "all existing images."
        ),
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # Find post
    # -----------------------------------------------------

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id
        )
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    # -----------------------------------------------------
    # Ownership
    # -----------------------------------------------------

    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=(
                "You can only update "
                "your own posts"
            ),
        )

    # -----------------------------------------------------
    # Active subscription
    # -----------------------------------------------------

    plan = get_active_subscription_plan(
        current_user
    )

    # -----------------------------------------------------
    # Update title
    # -----------------------------------------------------

    if title is not None:

        cleaned_title = (
            title.strip()
        )

        if not cleaned_title:

            raise HTTPException(
                status_code=422,
                detail="Title cannot be empty",
            )

        post.title = cleaned_title

    # -----------------------------------------------------
    # Update content
    # -----------------------------------------------------

    if content is not None:

        cleaned_content = (
            content.strip()
        )

        if not cleaned_content:

            raise HTTPException(
                status_code=422,
                detail="Content cannot be empty",
            )

        post.content = cleaned_content

    # -----------------------------------------------------
    # Replace all images
    # -----------------------------------------------------
    #
    # IMPORTANT:
    # If no images are selected, existing images
    # remain unchanged.
    # -----------------------------------------------------

    if images:

        image_count = len(images)

        # Check plan image limit
        if not plan.can_upload_images(
            image_count
        ):
            raise HTTPException(
                status_code=403,
                detail=PLAN_LIMIT_MESSAGE,
            )

        # Save new images first
        new_image_urls = (
            save_uploaded_images(
                images
            )
        )

        # Save old URLs before changing DB
        old_image_urls = (
            get_post_image_urls(
                post
            )
        )

        try:

            # -------------------------------------------------
            # Remove old PostImage rows
            # -------------------------------------------------

            for post_image in list(
                post.post_images
            ):

                db.delete(
                    post_image
                )

            # -------------------------------------------------
            # Replace first image
            # -------------------------------------------------

            post.image = (
                new_image_urls[0]
            )

            # -------------------------------------------------
            # Add additional images
            # -------------------------------------------------

            for image_url in (
                new_image_urls[1:]
            ):

                post_image = PostImage(
                    post_id=post.id,
                    image_url=image_url,
                )

                db.add(
                    post_image
                )

            db.commit()

            db.refresh(post)

            # -------------------------------------------------
            # Delete old files ONLY after successful commit
            # -------------------------------------------------

            for old_image_url in (
                old_image_urls
            ):

                delete_image_file(
                    old_image_url
                )

            return post

        except Exception:

            db.rollback()

            # Remove newly uploaded files
            for image_url in (
                new_image_urls
            ):

                delete_image_file(
                    image_url
                )

            raise

    # -----------------------------------------------------
    # Save title/content changes
    # -----------------------------------------------------

    db.commit()

    db.refresh(post)

    return post


# =========================================================
# DELETE POST
# =========================================================

@router.delete(
    "/{post_id}",
    summary="Delete a post",
)
def delete_post(
    post_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):
    # -----------------------------------------------------
    # Find post
    # -----------------------------------------------------

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id
        )
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=404,
            detail="Post not found",
        )

    # -----------------------------------------------------
    # Ownership
    # -----------------------------------------------------

    if post.author_id != current_user.id:

        raise HTTPException(
            status_code=403,
            detail=(
                "You can only delete "
                "your own posts"
            ),
        )

    # -----------------------------------------------------
    # Store image URLs before deleting post
    # -----------------------------------------------------

    image_urls = get_post_image_urls(
        post
    )

    try:

        db.delete(post)

        db.commit()

    except Exception:

        db.rollback()
        raise

    # -----------------------------------------------------
    # Delete files after successful DB delete
    # -----------------------------------------------------

    for image_url in image_urls:

        delete_image_file(
            image_url
        )

    return {
        "message": "Post deleted successfully"
    }