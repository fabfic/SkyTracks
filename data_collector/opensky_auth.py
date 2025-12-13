import os
import time
import requests
from typing import Optional, Tuple
from logging_utils import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

CACHED_TOKEN: Optional[str] = None
TOKEN_EXPIRATION: float = 0.0

OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID")
OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET")


class OpenSkyAuthError(Exception):
    """
    Exception raised for OpenSky authentication-related errors.
    The error is logged automatically when instantiated.
    """
    def __init__(self, message):
        logger.error(f"OpenSky Authentication Error: {message}")
        super().__init__(message)


def _request_new_token() -> Tuple[str, float]:
    """
    Request a new OAuth2 access token from OpenSky.
    Returns:
        Tuple[str, float]
            A tuple containing:
            - the access token
            - the absolute expiration timestamp (epoch seconds)
    Raises:
        OpenSkyAuthError
            If the token request fails or the response is invalid.
    """
    
    data = {
        "grant_type": "client_credentials",
        "client_id": OPENSKY_CLIENT_ID,
        "client_secret": OPENSKY_CLIENT_SECRET,
    }

    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10
    )

    if response.status_code != 200:
        raise OpenSkyAuthError(
            f"Token request failed (HTTP {response.status_code}): {response.text}"
        )

    payload = response.json()
    token = payload.get("access_token")
    expires_in = payload.get("expires_in", 300)

    if not token:
        raise OpenSkyAuthError("Missing access_token in response")

    return token, time.time() + expires_in


def get_opensky_token() -> str:
    """
    Retrieve a valid OpenSky access token.
    Returns:
        str
            The valid access token.
    Raises:
        OpenSkyAuthError
            If authentication fails or credentials are missing.
    """

    global CACHED_TOKEN, TOKEN_EXPIRATION

    if not OPENSKY_CLIENT_ID or not OPENSKY_CLIENT_SECRET:
        raise OpenSkyAuthError("CLIENT_ID or CLIENT_SECRET not set")

    now = time.time()

    # Token still valid
    if CACHED_TOKEN and now < TOKEN_EXPIRATION - 60:
        return CACHED_TOKEN

    # Need a new token
    CACHED_TOKEN, TOKEN_EXPIRATION = _request_new_token()

    return CACHED_TOKEN