from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # S3
    s3_images_bucket: str = "sumo-dashboard-images"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    allowed_domain: str = "example.com"

    # Session
    session_secret_key: str = "change-me"

    # API keys
    ssm_api_keys_prefix: str = "/sumo-viewer/api-keys/"

    # Staleness
    stale_threshold_minutes: int = 30

    # Mock mode
    mock_mode: bool = False
    mock_data_dir: str = "mock-data"
    mock_auth: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
