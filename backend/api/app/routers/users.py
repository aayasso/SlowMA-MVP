"""
SlowMA Users Router
Authentication, profile management, and user statistics.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import (
    AuthResponse,
    MagicLinkRequest,
    PasswordResetRequest,
    PasswordUpdateRequest,
    SignInRequest,
    SignUpRequest,
    UserProfileResponse,
    UserProfileUpdate,
    UserStatsResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and verify the user from the Authorization header."""
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


STAGE_NAMES = {1: "Accountive", 2: "Constructive", 3: "Classifying", 4: "Interpretive", 5: "Re-creative"}
SUBSTAGE_NAMES = {1: "Early", 2: "Developing", 3: "Advanced"}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=AuthResponse)
async def sign_up(body: SignUpRequest, db: Client = Depends(get_supabase)):
    """Register a new user with email & password."""
    try:
        auth_response = db.auth.sign_up({"email": body.email, "password": body.password})

        if not auth_response.user:
            return AuthResponse(success=False, error="Failed to create account")

# Create the user_profiles row
        profile = {
            "id": auth_response.user.id,
            "email": body.email,
            "display_name": body.display_name,
            "housen_stage": 1,
            "housen_substage": 1,
            "total_journeys": 0,
            "is_teacher": False,
        }
        db.table("user_profiles").insert(profile).execute()

        session = auth_response.session
        return AuthResponse(
            success=True,
            message="Account created successfully!",
            access_token=session.access_token if session else None,
            refresh_token=session.refresh_token if session else None,
            user_id=auth_response.user.id,
        )
    except Exception as exc:
        msg = str(exc)
        if "already registered" in msg.lower():
            msg = "This email is already registered. Try signing in instead."
        return AuthResponse(success=False, error=msg)


@router.post("/signin", response_model=AuthResponse)
async def sign_in(body: SignInRequest, db: Client = Depends(get_supabase)):
    """Sign in with email & password."""
    try:
        auth_response = db.auth.sign_in_with_password({"email": body.email, "password": body.password})
        if not auth_response.user:
            return AuthResponse(success=False, error="Invalid email or password")

        session = auth_response.session
        return AuthResponse(
            success=True,
            access_token=session.access_token if session else None,
            refresh_token=session.refresh_token if session else None,
            user_id=auth_response.user.id,
        )
    except Exception as exc:
        msg = str(exc)
        if "invalid" in msg.lower() or "credentials" in msg.lower():
            msg = "Invalid email or password"
        return AuthResponse(success=False, error=msg)


@router.post("/magic-link", response_model=AuthResponse)
async def magic_link(body: MagicLinkRequest, db: Client = Depends(get_supabase)):
    """Send a passwordless magic-link email."""
    try:
        db.auth.sign_in_with_otp({"email": body.email})
        return AuthResponse(success=True, message="Magic link sent! Check your email.")
    except Exception as exc:
        return AuthResponse(success=False, error=str(exc))


@router.post("/signout", response_model=AuthResponse)
async def sign_out(db: Client = Depends(get_supabase)):
    """Sign out the current session."""
    try:
        db.auth.sign_out()
        return AuthResponse(success=True, message="Signed out successfully")
    except Exception as exc:
        return AuthResponse(success=False, error=str(exc))


@router.post("/password-reset", response_model=AuthResponse)
async def password_reset(body: PasswordResetRequest, db: Client = Depends(get_supabase)):
    """Send a password reset email."""
    try:
        db.auth.reset_password_email(body.email)
        return AuthResponse(success=True, message="Password reset email sent")
    except Exception as exc:
        return AuthResponse(success=False, error=str(exc))


@router.post("/password-update", response_model=AuthResponse)
async def password_update(body: PasswordUpdateRequest, db: Client = Depends(get_supabase)):
    """Update the current user's password (requires valid session)."""
    try:
        db.auth.update_user({"password": body.new_password})
        return AuthResponse(success=True, message="Password updated successfully")
    except Exception as exc:
        return AuthResponse(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Return the authenticated user's profile."""
    result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result.data[0]


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    updates: UserProfileUpdate,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Update editable profile fields."""
    data = updates.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    db.table("user_profiles").update(data).eq("id", user["id"]).execute()
    result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    return result.data[0]


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Return aggregate statistics for the current user."""
    profile_result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    if not profile_result.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    p = profile_result.data[0]
    stage = p.get("housen_stage", 1)
    substage = p.get("housen_substage", 1)

    return UserStatsResponse(
        total_journeys=p.get("journeys_completed", 0),
        total_minutes=p.get("total_time_seconds", 0) // 60,
        museum_visits=p.get("museum_visits", 0),
        current_stage=stage,
        current_substage=substage,
        stage_name=STAGE_NAMES.get(stage, "Unknown"),
        substage_name=SUBSTAGE_NAMES.get(substage, "Unknown"),
        current_streak=p.get("current_streak", 0),
    )


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: str, db: Client = Depends(get_supabase)):
    """Public profile lookup (limited fields could be enforced via RLS)."""
    result = db.table("user_profiles").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data[0]
