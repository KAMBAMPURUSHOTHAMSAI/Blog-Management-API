from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import (
    SubscriptionPlan,
    User,
    utc_now,
)
from app.schemas import (
    Token,
    UserCreate,
    UserResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# Register
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    # ========================================================
    # Check Duplicate Username
    # ========================================================

    existing_username = (
        db.query(User)
        .filter(
            User.username == user_data.username
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # ========================================================
    # Check Duplicate Email
    # ========================================================

    existing_email = (
        db.query(User)
        .filter(
            User.email == user_data.email
        )
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    # ========================================================
    # Find Basic Plan
    # ========================================================

    basic_plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.name == "Basic",
            SubscriptionPlan.is_active == True,
        )
        .first()
    )

    if basic_plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Basic subscription plan is not available. "
                "Please contact the administrator."
            ),
        )

    # ========================================================
    # Hash Password
    # ========================================================

    hashed_password = hash_password(
        user_data.password
    )

    # ========================================================
    # Create User
    # ========================================================

    start_date = utc_now()

    end_date = (
        start_date
        + timedelta(
            days=basic_plan.duration_days
        )
    )

    user = User(
        username=user_data.username,
        email=user_data.email,
        password=hashed_password,

        # Automatically assign Basic plan
        subscription_plan_id=basic_plan.id,

        # Basic subscription validity
        subscription_start_date=start_date,
        subscription_end_date=end_date,
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return user


# ============================================================
# Login
# ============================================================

@router.post(
    "/login",
    response_model=Token,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # ========================================================
    # Find User by Username
    # ========================================================

    user = (
        db.query(User)
        .filter(
            User.username == form_data.username
        )
        .first()
    )

    # ========================================================
    # Verify Credentials
    # ========================================================

    if user is None or not verify_password(
        form_data.password,
        user.password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # ========================================================
    # Create JWT Token
    # ========================================================

    access_token = create_access_token(
        user.id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }