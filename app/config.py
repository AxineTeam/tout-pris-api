from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    brevo_api_key: str = ""
    mail_from_email: str = "no-reply@tout-pris.app"
    mail_from_name: str = "Tout Pris"


settings = Settings()
