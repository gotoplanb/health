from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def verify_hd_claim(user_info: dict) -> bool:
    """Verify the user's hosted domain matches the allowed domain."""
    return user_info.get("hd") == settings.allowed_domain
