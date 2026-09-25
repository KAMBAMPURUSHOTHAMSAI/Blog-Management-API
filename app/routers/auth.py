import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
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
# Constants
# ============================================================

PENDING_SOCIAL_COOKIE = "pending_social_auth"


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
# Complete Social Profile Page
# ============================================================

@router.get(
    "/complete-profile",
    include_in_schema=False,
)
def complete_profile_page():
    """
    Serve the page used when Auth0 does not return
    the user's email address.
    """

    profile_file = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "complete_profile.html"
    )

    if not profile_file.exists():
        raise FileNotFoundError(
            f"Complete profile page not found: {profile_file}"
        )

    return FileResponse(
        path=profile_file,
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
    # Generate a random password so the existing DB
    # structure remains unchanged.
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
        auth_provider=provider,
        auth_provider_id=provider_id,
        subscription_plan_id=basic_plan.id,
        subscription_start_date=start_date,
        subscription_end_date=end_date,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# ============================================================
# Helper: Create Pending Social Login Token
# ============================================================

def create_pending_social_token(
    provider: str,
    provider_id: str,
    name: str,
) -> str:
    """
    Create a short-lived signed token used when
    Auth0 does not return the email address.
    """

    payload = {
        "provider": provider,
        "provider_id": provider_id,
        "name": name,
        "exp": int(time.time()) + 600,  # 10 minutes
    }

    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    encoded_payload = (
        base64.urlsafe_b64encode(payload_json)
        .decode("utf-8")
        .rstrip("=")
    )

    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    encoded_signature = (
        base64.urlsafe_b64encode(signature)
        .decode("utf-8")
        .rstrip("=")
    )

    return f"{encoded_payload}.{encoded_signature}"


# ============================================================
# Helper: Verify Pending Social Login Token
# ============================================================

def verify_pending_social_token(
    token: str,
):
    """
    Verify the signed pending social login token.
    """

    try:
        encoded_payload, encoded_signature = token.split(
            ".",
            1,
        )

        expected_signature = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            encoded_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        provided_signature = base64.urlsafe_b64decode(
            encoded_signature
            + "="
            * (-len(encoded_signature) % 4)
        )

        if not hmac.compare_digest(
            expected_signature,
            provided_signature,
        ):
            return None

        payload_bytes = base64.urlsafe_b64decode(
            encoded_payload
            + "="
            * (-len(encoded_payload) % 4)
        )

        payload = json.loads(
            payload_bytes.decode("utf-8")
        )

        if payload.get("exp", 0) < int(time.time()):
            return None

        if not payload.get("provider_id"):
            return None

        if not payload.get("provider"):
            return None

        return payload

    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        return None


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
        auth_provider=None,
        auth_provider_id=None,
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
    # Create Application JWT
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
    # Store OAuth State In Cookie
    # ========================================================

    redirect_response.set_cookie(
        key="auth0_state",
        value=state,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=600,
    )

    return redirect_response


# ============================================================
# Complete Social Profile
# ============================================================

@router.post(
    "/complete-profile",
    include_in_schema=False,
)
def complete_profile(
    request: Request,
    email: EmailStr = Form(...),
    db: Session = Depends(get_db),
):
    """
    Complete the local profile when Auth0 does not
    provide the email address.
    """

    # ========================================================
    # Get Pending Social Session
    # ========================================================

    pending_token = request.cookies.get(
        PENDING_SOCIAL_COOKIE
    )

    if not pending_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Social login session has expired. "
                "Please login again."
            ),
        )

    # ========================================================
    # Verify Pending Token
    # ========================================================

    payload = verify_pending_social_token(
        pending_token
    )

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired social login session.",
        )

    provider = payload["provider"]
    provider_id = payload["provider_id"]
    name = payload.get("name") or ""

    normalized_email = (
        str(email).strip().lower()
    )

    # ========================================================
    # Check Existing Social Account
    # ========================================================

    existing_social_user = (
        db.query(User)
        .filter(
            User.auth_provider_id == provider_id
        )
        .first()
    )

    if existing_social_user:

        application_token = create_access_token(
            existing_social_user.id
        )

        dashboard_url = (
            "/user/dashboard/page"
            f"#access_token="
            f"{quote(application_token, safe='')}"
        )

        redirect_response = RedirectResponse(
            url=dashboard_url,
            status_code=status.HTTP_302_FOUND,
        )

        redirect_response.delete_cookie(
            key=PENDING_SOCIAL_COOKIE
        )

        return redirect_response

    # ========================================================
    # Check Existing Email
    # ========================================================

    existing_email_user = (
        db.query(User)
        .filter(
            User.email == normalized_email
        )
        .first()
    )

    # ========================================================
    # Existing User Found
    # Link Social Provider To Existing User
    # ========================================================

    if existing_email_user:

        existing_email_user.auth_provider = provider
        existing_email_user.auth_provider_id = provider_id

        db.commit()
        db.refresh(existing_email_user)

        application_token = create_access_token(
            existing_email_user.id
        )

        dashboard_url = (
            "/user/dashboard/page"
            f"#access_token="
            f"{quote(application_token, safe='')}"
        )

        redirect_response = RedirectResponse(
            url=dashboard_url,
            status_code=status.HTTP_302_FOUND,
        )

        redirect_response.delete_cookie(
            key=PENDING_SOCIAL_COOKIE
        )

        return redirect_response

    # ========================================================
    # Create New Social User
    # ========================================================

    user = create_social_user(
        db=db,
        name=name,
        email=normalized_email,
        provider=provider,
        provider_id=provider_id,
    )

    # ========================================================
    # Create Application JWT
    # ========================================================

    application_token = create_access_token(
        user.id
    )

    # ========================================================
    # Redirect To Dashboard
    # ========================================================

    dashboard_url = (
        "/user/dashboard/page"
        f"#access_token="
        f"{quote(application_token, safe='')}"
    )

    redirect_response = RedirectResponse(
        url=dashboard_url,
        status_code=status.HTTP_302_FOUND,
    )

    redirect_response.delete_cookie(
        key=PENDING_SOCIAL_COOKIE
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
    # Social Email Fallback
    # ========================================================

    if not email:

        # ====================================================
        # Check Existing Social User
        # ====================================================

        existing_social_user = (
            db.query(User)
            .filter(
                User.auth_provider_id == provider_id
            )
            .first()
        )

        # ====================================================
        # Existing Social User
        # ====================================================

        if existing_social_user:

            application_token = create_access_token(
                existing_social_user.id
            )

            dashboard_url = (
                "/user/dashboard/page"
                f"#access_token="
                f"{quote(application_token, safe='')}"
            )

            redirect_response = RedirectResponse(
                url=dashboard_url,
                status_code=status.HTTP_302_FOUND,
            )

            redirect_response.delete_cookie(
                key="auth0_state"
            )

            return redirect_response

        # ====================================================
        # Create Pending Social Login Session
        # ====================================================

        pending_token = create_pending_social_token(
            provider=provider,
            provider_id=provider_id,
            name=name,
        )

        redirect_response = RedirectResponse(
            url="/auth/complete-profile",
            status_code=status.HTTP_302_FOUND,
        )

        redirect_response.set_cookie(
            key=PENDING_SOCIAL_COOKIE,
            value=pending_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=600,
        )

        redirect_response.delete_cookie(
            key="auth0_state"
        )

        return redirect_response

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
    # Issue Application JWT
    # ========================================================

    application_token = create_access_token(
        user.id
    )

    # ========================================================
    # Redirect To Dashboard
    # ========================================================

    dashboard_url = (
        "/user/dashboard/page"
        f"#access_token="
        f"{quote(application_token, safe='')}"
    )

    redirect_response = RedirectResponse(
        url=dashboard_url,
        status_code=status.HTTP_302_FOUND,
    )

    # ========================================================
    # Remove Auth0 State Cookie
    # ========================================================

    redirect_response.delete_cookie(
        key="auth0_state",
    )

    return redirect_response