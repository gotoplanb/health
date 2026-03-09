import boto3

from app.config import settings

_valid_keys: set[str] = set()


def load_api_keys() -> None:
    """Load API keys from SSM Parameter Store into memory."""
    global _valid_keys
    if settings.mock_mode:
        # In mock mode, accept a hardcoded dev key
        _valid_keys = {"dev-api-key"}
        return

    client = boto3.client("ssm")
    paginator = client.get_paginator("get_parameters_by_path")
    keys = set()
    for page in paginator.paginate(
        Path=settings.ssm_api_keys_prefix,
        WithDecryption=True,
    ):
        for param in page["Parameters"]:
            keys.add(param["Value"])
    _valid_keys = keys


def is_valid_api_key(key: str) -> bool:
    """Check if a given API key is valid."""
    return key in _valid_keys
