import math
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Post, User
from app.schemas import (
    PaginatedPostsResponse,
    PostResponse,
)


router = APIRouter(
    prefix="/posts",
    tags=["Posts"],
)


# ============================================================
# Configuration
# ============================================================

MEDIA_ROOT = Path("media")
POSTS_MEDIA_DIR = MEDIA_ROOT / "posts"

# Create media/posts automatically if it does not exist
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

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


# ============================================================
# Helper - Save Uploaded Image
# ============================================================

def save_uploaded_image(
    image: UploadFile,
) -> str:
    """
    Validate and save an uploaded image.

    Returns:
        Relative URL path such as:
        /media/posts/abc123.jpg
    """

    if not image.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image filename is missing",
        )

    extension = Path(
        image.filename
    ).suffix.lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported image format. "
                "Allowed formats: JPG, JPEG, PNG, GIF, WEBP"
            ),
        )

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a valid image",
        )

    # Read the image
    file_data = image.file.read()

    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    if len(file_data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must be 5 MB or less",
        )

    # Generate a unique filename
    unique_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    file_path = POSTS_MEDIA_DIR / unique_filename

    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(file_data)

    # Return browser-accessible URL
    return f"/media/posts/{unique_filename}"


# ============================================================
# Helper - Delete Existing Image
# ============================================================

def delete_image_file(
    image_url: str | None,
) -> None:
    """
    Delete an existing post image from disk.
    """

    if not image_url:
        return

    filename = Path(image_url).name

    if not filename:
        return

    file_path = POSTS_MEDIA_DIR / filename

    if file_path.exists():
        file_path.unlink()


# ============================================================
# CREATE POST
# ============================================================

@router.post(
    "/create",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new post with optional image",
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
    image: UploadFile | None = File(
        default=None,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_url = None

    if image is not None:
        image_url = save_uploaded_image(image)

    post = Post(
        title=title.strip(),
        content=content.strip(),
        image=image_url,
        author_id=current_user.id,
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    return post


# ============================================================
# GET ALL POSTS - SEARCH + PAGINATION
# ============================================================

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
    # Validate pagination
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than or equal to 1",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100",
        )

    # Base query
    query = db.query(Post)

    # Search in title OR content
    if search and search.strip():
        search_value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Post.title.ilike(search_value),
                Post.content.ilike(search_value),
            )
        )

    # Total count before pagination
    total_count = query.count()

    # Calculate total pages
    total_pages = (
        math.ceil(total_count / limit)
        if total_count > 0
        else 0
    )

    # Calculate offset
    offset = (page - 1) * limit

    posts = (
        query
        .order_by(Post.created_at.desc())
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


# ============================================================
# GET MY POSTS
# ============================================================

@router.get(
    "/mine",
    response_model=list[PostResponse],
    summary="Get current user's posts",
)
def get_my_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    posts = (
        db.query(Post)
        .filter(
            Post.author_id == current_user.id
        )
        .order_by(Post.created_at.desc())
        .all()
    )

    return posts


# ============================================================
# GET SINGLE POST
# ============================================================

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
        .filter(Post.id == post_id)
        .first()
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return post


# ============================================================
# UPDATE POST - OWNER ONLY
# ============================================================

@router.put(
    "/{post_id}/update",
    response_model=PostResponse,
    summary="Update a post with optional image",
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
    image: UploadFile | None = File(
        default=None,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    # Ownership check
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own posts",
        )

    # Update title
    if title is not None:
        cleaned_title = title.strip()

        if not cleaned_title:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Title cannot be empty",
            )

        post.title = cleaned_title

    # Update content
    if content is not None:
        cleaned_content = content.strip()

        if not cleaned_content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Content cannot be empty",
            )

        post.content = cleaned_content

    # Replace image if a new image is uploaded
    if image is not None:
        old_image = post.image

        new_image_url = save_uploaded_image(image)

        post.image = new_image_url

        # Delete old image after successfully saving new image
        delete_image_file(old_image)

    db.commit()
    db.refresh(post)

    return post


# ============================================================
# DELETE POST - OWNER ONLY
# ============================================================

@router.delete(
    "/{post_id}",
    summary="Delete a post",
)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    # Ownership check
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts",
        )

    # Delete associated image
    delete_image_file(post.image)

    db.delete(post)
    db.commit()

    return {
        "message": "Post deleted successfully"
    }