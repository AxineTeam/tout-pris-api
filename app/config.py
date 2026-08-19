from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "development-secret-key-not-for-production-use"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    brevo_api_key: str = ""
    mail_from_email: str = "no-reply@tout-pris.app"
    mail_from_name: str = "Tout Pris"


settings = Settings()
