from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AISupportChat, User
from app.schemas import (
    AISupportChatListResponse,
    AISupportRequest,
    AISupportResponse,
)
from app.services.ai_support_service import (
    generate_ai_response,
)


# =========================================================
# Router
# =========================================================

router = APIRouter(
    prefix="/api/ai-support",
    tags=["AI Support"],
)


# =========================================================
# Send Message to AI Support
# =========================================================

@router.post(
    "/",
    response_model=AISupportResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the AI Support Assistant",
)
def ask_ai_support(
    request: AISupportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a support question from the authenticated user,
    generate an AI/FAQ response, save the conversation,
    and return the response.
    """

    # =====================================================
    # Clean User Message
    # =====================================================

    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty.",
        )

    # =====================================================
    # Generate AI Response
    # =====================================================

    try:
        ai_response = generate_ai_response(
            message
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to generate an AI support response "
                "at this time."
            ),
        )

    # =====================================================
    # Save Chat Activity
    # =====================================================

    chat = AISupportChat(
        user_id=current_user.id,
        question=message,
        ai_response=ai_response,
    )

    try:
        db.add(chat)

        db.commit()

        db.refresh(chat)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The AI response was generated, but the "
                "chat history could not be saved."
            ),
        )

    # =====================================================
    # Return AI Response
    # =====================================================

    return {
        "reply": ai_response
    }


# =========================================================
# Get AI Support Chat History
# =========================================================

@router.get(
    "/history",
    response_model=AISupportChatListResponse,
    summary="Get current user's AI support history",
)
def get_ai_support_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated user's previous AI Support
    conversations.
    """

    # =====================================================
    # Validate Limit
    # =====================================================

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 100.",
        )

    # =====================================================
    # Get Current User's Chat History
    # =====================================================

    chats = (
        db.query(AISupportChat)
        .filter(
            AISupportChat.user_id
            == current_user.id
        )
        .order_by(
            AISupportChat.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    return {
        "chats": chats
    }