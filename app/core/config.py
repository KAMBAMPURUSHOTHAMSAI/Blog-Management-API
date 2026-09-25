from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # =====================================================
    # Database
    # =====================================================

    DATABASE_URL: str

    # =====================================================
    # JWT Authentication
    # =====================================================

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # =====================================================
    # SMTP / Email Configuration
    # =====================================================

    SMTP_HOST: str = ""

    SMTP_PORT: int = 465

    SMTP_USERNAME: str = ""

    SMTP_PASSWORD: str = ""

    EMAIL_FROM: str = ""

    # -----------------------------------------------------
    # SMTP Security
    # -----------------------------------------------------

    SMTP_SSL: bool = True

    SMTP_TLS: bool = False

    # =====================================================
    # Auth0 Configuration
    # =====================================================

    AUTH0_DOMAIN: str = ""

    AUTH0_CLIENT_ID: str = ""

    AUTH0_CLIENT_SECRET: str = ""

    AUTH0_CALLBACK_URL: str = (
        "http://127.0.0.1:8000/auth/callback/"
    )

    AUTH0_LOGOUT_URL: str = (
        "http://127.0.0.1:8000/"
    )

    AUTH0_AUDIENCE: str = ""

    # =====================================================
    # Environment Configuration
    # =====================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()