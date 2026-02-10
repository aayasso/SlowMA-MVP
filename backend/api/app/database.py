"""
SlowMA Database Client
Supabase client initialization and helper utilities.
"""

import os
from functools import lru_cache
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class SupabaseClient:
    """Singleton wrapper around the Supabase Python client."""

    _instance: Client | None = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_ANON_KEY")
            if not url or not key:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables. "
                    "Copy .env.example to .env and fill in your Supabase project credentials."
                )
            cls._instance = create_client(url, key)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the client (useful for testing)."""
        cls._instance = None


def get_supabase() -> Client:
    """FastAPI dependency — returns the shared Supabase client."""
    return SupabaseClient.get_client()


def get_authenticated_client(access_token: str) -> Client:
    """
    Return a Supabase client scoped to a specific user session.
    This sets the Authorization header so Row-Level Security policies apply.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Supabase credentials not configured")

    client = create_client(url, key)
    client.postgrest.auth(access_token)
    return client


def verify_token(access_token: str) -> dict | None:
    """
    Verify a Supabase JWT and return the user payload, or None if invalid.
    """
    try:
        client = get_supabase()
        user_response = client.auth.get_user(access_token)
        if user_response and user_response.user:
            return {
                "id": user_response.user.id,
                "email": user_response.user.email,
                "role": user_response.user.role,
            }
        return None
    except Exception:
        return None