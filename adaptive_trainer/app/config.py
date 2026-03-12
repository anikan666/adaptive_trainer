from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str
    whatsapp_verify_token: str
    whatsapp_access_token: str
    whatsapp_app_secret: str
    whatsapp_phone_number_id: str
    database_url: str


settings = Settings()
