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
    # Gmail:
    #   SMTP_SSL = True
    #   SMTP_TLS = False
    #
    # Mailtrap Sandbox:
    #   SMTP_SSL = False
    #   SMTP_TLS = True
    # -----------------------------------------------------

    SMTP_SSL: bool = True

    SMTP_TLS: bool = False

    # =====================================================
    # Environment Configuration
    # =====================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()