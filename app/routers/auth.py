from pathlib import Path
import secrets
from datetime import timedelta
from urllib.parse import quote, urlencode

import httpx

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
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
# Authentication Web Page
# ============================================================

@router.get(
    "/page",
    include_in_schema=False,
)
def auth_page():
    """
    Serve the Login / Signup HTML page.
    """

    auth_file = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "login.html"
    )

    if not auth_file.exists():
        raise FileNotFoundError(
            f"Authentication page not found: {auth_file}"
        )

    return FileResponse(
        path=auth_file,
        media_type="text/html",
    )


# ============================================================
# Helper: Basic Subscription Plan
# ============================================================

def get_basic_plan(db: Session):
    """
    Get the active Basic subscription plan.
    """

    basic_plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.name == "Basic",
            SubscriptionPlan.is_active.is_(True),
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

    return basic_plan


# ============================================================
# Helper: Create Unique Username
# ============================================================

def create_unique_username(
    db: Session,
    base_username: str,
) -> str:
    """
    Create a unique local username for an Auth0 user.
    """

    # Keep only safe username characters
    cleaned_username = "".join(
        character
        for character in base_username
        if character.isalnum() or character in "._-"
    )

    cleaned_username = cleaned_username.strip("._-")

    if not cleaned_username:
        cleaned_username = "user"

    # Respect database username limit
    cleaned_username = cleaned_username[:40]

    username = cleaned_username
    counter = 1

    while (
        db.query(User)
        .filter(User.username == username)
        .first()
        is not None
    ):
        username = f"{cleaned_username}{counter}"
        counter += 1

    return username


# ============================================================
# Helper: Create Local User For Social Login
# ============================================================

def create_social_user(
    db: Session,
    name: str,
    email: str,
    provider: str,
    provider_id: str,
):
    """
    Create a local user after successful Auth0 login.
    """

    basic_plan = get_basic_plan(db)

    # Create username from name/email
    username_source = name.strip()

    if not username_source:
        username_source = email.split("@")[0]

    username = create_unique_username(
        db,
        username_source,
    )

    # Social users do not use local password login.
    # Generate a random password so existing DB structure
    # remains unchanged.
    random_password = secrets.token_urlsafe(32)

    hashed_password = hash_password(
        random_password
    )

    # Subscription dates
    start_date = utc_now()

    end_date = (
        start_date
        + timedelta(
            days=basic_plan.duration_days
        )
    )

    # Create local user
    user = User(
        username=username,
        email=email,
        password=hashed_password,

        # Auth0 / Social login information
        auth_provider=provider,
        auth_provider_id=provider_id,

        # Automatically assign Basic plan
        subscription_plan_id=basic_plan.id,
        subscription_start_date=start_date,
        subscription_end_date=end_date,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# ============================================================
# Register / Signup
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Normal email/password signup.

    Available endpoints:
        POST /auth/register
        POST /auth/signup
    """

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

    basic_plan = get_basic_plan(db)

    # ========================================================
    # Hash Password
    # ========================================================

    hashed_password = hash_password(
        user_data.password
    )

    # ========================================================
    # Subscription Dates
    # ========================================================

    start_date = utc_now()

    end_date = (
        start_date
        + timedelta(
            days=basic_plan.duration_days
        )
    )

    # ========================================================
    # Create Normal User
    # ========================================================

    user = User(
        username=user_data.username,
        email=user_data.email,
        password=hashed_password,

        # Normal signup
        auth_provider=None,
        auth_provider_id=None,

        # Basic subscription
        subscription_plan_id=basic_plan.id,
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
    """
    Normal username/password login.
    """

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
    # User Not Found
    # ========================================================

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # ========================================================
    # Verify Password
    # ========================================================

    if not verify_password(
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
    # Create Existing Application JWT
    # ========================================================

    access_token = create_access_token(
        user.id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ============================================================
# Auth0 Login
# ============================================================

@router.get(
    "/auth0/login",
)
def auth0_login(
    connection: str = "google-oauth2",
):
    """
    Redirect user to Auth0.

    Google:
        /auth/auth0/login?connection=google-oauth2

    Facebook:
        /auth/auth0/login?connection=facebook
    """

    # ========================================================
    # Validate Auth0 Configuration
    # ========================================================

    if not settings.AUTH0_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_DOMAIN is not configured",
        )

    if not settings.AUTH0_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_CLIENT_ID is not configured",
        )

    if not settings.AUTH0_CALLBACK_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_CALLBACK_URL is not configured",
        )

    # ========================================================
    # Allow Only Configured Social Connections
    # ========================================================

    allowed_connections = {
        "google-oauth2",
        "facebook",
    }

    if connection not in allowed_connections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported Auth0 connection",
        )

    # ========================================================
    # Generate OAuth State
    # ========================================================

    state = secrets.token_urlsafe(32)

    # ========================================================
    # Build Auth0 Authorization URL
    # ========================================================

    authorize_url = (
        f"https://{settings.AUTH0_DOMAIN}"
        "/authorize"
    )

    params = {
        "response_type": "code",
        "client_id": settings.AUTH0_CLIENT_ID,
        "redirect_uri": settings.AUTH0_CALLBACK_URL,
        "scope": "openid profile email",
        "state": state,
        "connection": connection,
        "prompt": "consent",
    }

    # Add Auth0 API audience only when configured
    if settings.AUTH0_AUDIENCE:
        params["audience"] = settings.AUTH0_AUDIENCE

    auth0_url = (
        f"{authorize_url}?{urlencode(params)}"
    )

    # ========================================================
    # Redirect To Auth0
    # ========================================================

    redirect_response = RedirectResponse(
        url=auth0_url,
        status_code=status.HTTP_302_FOUND,
    )

    # ========================================================
    # Store OAuth State In Secure HttpOnly Cookie
    # ========================================================

    redirect_response.set_cookie(
        key="auth0_state",
        value=state,
        httponly=True,
        secure=False,      # False for local HTTP development
        samesite="lax",
        max_age=600,
    )

    return redirect_response


# ============================================================
# Auth0 Callback
# ============================================================

@router.get(
    "/callback/",
)
def auth0_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Auth0 callback endpoint.

    Auth0 redirects the user here after
    Google/Facebook authentication.
    """

    # ========================================================
    # Handle Auth0 Error
    # ========================================================

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                error_description
                or error
                or "Auth0 authentication failed"
            ),
        )

    # ========================================================
    # Validate Code
    # ========================================================

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is missing",
        )

    # ========================================================
    # Validate State
    # ========================================================

    stored_state = request.cookies.get(
        "auth0_state"
    )

    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth0 state is missing",
        )

    if not stored_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth0 state cookie is missing",
        )

    if not secrets.compare_digest(
        state,
        stored_state,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Auth0 state",
        )

    # ========================================================
    # Validate Auth0 Client Configuration
    # ========================================================

    if not settings.AUTH0_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_DOMAIN is not configured",
        )

    if not settings.AUTH0_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_CLIENT_ID is not configured",
        )

    if not settings.AUTH0_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH0_CLIENT_SECRET is not configured",
        )

    # ========================================================
    # Exchange Authorization Code For Auth0 Tokens
    # ========================================================

    token_url = (
        f"https://{settings.AUTH0_DOMAIN}"
        "/oauth/token"
    )

    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.AUTH0_CALLBACK_URL,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            token_response = client.post(
                token_url,
                data=token_data,
            )

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to Auth0",
        )

    # ========================================================
    # Check Token Exchange Response
    # ========================================================

    if token_response.status_code != 200:

        try:
            auth0_error = token_response.json()
        except ValueError:
            auth0_error = {}

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth0_error.get(
                "error_description",
                "Auth0 token exchange failed",
            ),
        )

    # ========================================================
    # Parse Auth0 Token Response
    # ========================================================

    try:
        token_json = token_response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid token response received from Auth0",
        )

    auth0_access_token = token_json.get(
        "access_token"
    )

    if not auth0_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth0 access token was not returned",
        )

    # ========================================================
    # Get User Information From Auth0
    # ========================================================

    userinfo_url = (
        f"https://{settings.AUTH0_DOMAIN}"
        "/userinfo"
    )

    try:
        with httpx.Client(timeout=15.0) as client:

            userinfo_response = client.get(
                userinfo_url,
                headers={
                    "Authorization": (
                        f"Bearer {auth0_access_token}"
                    )
                },
            )

    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Unable to retrieve user information "
                "from Auth0"
            ),
        )

    # ========================================================
    # Validate Userinfo Response
    # ========================================================

    if userinfo_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Unable to retrieve authenticated "
                "user information"
            ),
        )

    try:
        auth0_user = userinfo_response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Invalid user information received "
                "from Auth0"
            ),
        )

    # ========================================================
    # Extract Auth0 User Information
    # ========================================================

    provider_id = auth0_user.get("sub")
    email = auth0_user.get("email")

    name = (
        auth0_user.get("name")
        or auth0_user.get("nickname")
        or ""
    )

    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth0 user ID is missing",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Email address was not provided by "
                "the social login provider"
            ),
        )

    # ========================================================
    # Detect Provider
    # ========================================================

    if provider_id.startswith(
        "google-oauth2|"
    ):
        provider = "google"

    elif provider_id.startswith(
        "facebook|"
    ):
        provider = "facebook"

    else:
        provider = provider_id.split(
            "|",
            1,
        )[0]

    # ========================================================
    # Find Existing Social User
    # ========================================================

    user = (
        db.query(User)
        .filter(
            User.auth_provider_id == provider_id
        )
        .first()
    )

    # ========================================================
    # If Not Found, Check Existing Email
    # ========================================================

    if user is None:

        user = (
            db.query(User)
            .filter(
                User.email == email
            )
            .first()
        )

        # ====================================================
        # Existing Local User
        # ====================================================

        if user is not None:

            user.auth_provider = provider
            user.auth_provider_id = provider_id

            db.commit()
            db.refresh(user)

        # ====================================================
        # New Social User
        # ====================================================

        else:

            user = create_social_user(
                db=db,
                name=name,
                email=email,
                provider=provider,
                provider_id=provider_id,
            )

    # ========================================================
    # Issue Existing Application JWT
    # ========================================================

    application_token = create_access_token(
        user.id
    )

    # ========================================================
    # Redirect To Dashboard With JWT
    # ========================================================

    dashboard_path = "/user/dashboard/page"

    dashboard_url = (
        f"{dashboard_path}"
        f"#access_token="
        f"{quote(application_token, safe='')}"
    )

    redirect_response = RedirectResponse(
        url=dashboard_url,
        status_code=status.HTTP_302_FOUND,
    )

    # ========================================================
    # Remove Temporary Auth0 State Cookie
    # ========================================================

    redirect_response.delete_cookie(
        key="auth0_state",
    )

    return redirect_response