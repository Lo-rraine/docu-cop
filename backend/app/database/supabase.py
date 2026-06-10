from supabase import Client, create_client

from ..config import settings


def get_service_role_client() -> Client:
    """Create a Supabase client with service role key (admin access)."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_user_client(user_jwt: str) -> Client:
    """Create a Supabase client scoped to a specific user with their JWT."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.auth.set_session(user_jwt)
    return client
