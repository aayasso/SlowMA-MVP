"""
SlowMA Users Router
Handles user authentication and profile management.
"""

import os

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from supabase import create_client
from app.database import get_supabase, verify_token, Client
from app.models.schemas import (
    SignUpRequest,
    SignInRequest,
    AuthResponse,
    UserProfileResponse,
    UserProfileUpdate,
    UserStatsResponse
)

router = APIRouter(prefix="/api/users", tags=["Users"])


# ============================================================
# Authentication Endpoints
# ============================================================

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest, db: Client = Depends(get_supabase)):
    try:
        auth_response = db.auth.sign_up({
            "email": request.email,
            "password": request.password,
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user account")

        user_id = auth_response.user.id

        profile_data = {
            "id": user_id,
            "email": request.email,
            "username": request.username or request.email.split("@")[0],
            "housen_stage": 1,
            "housen_substage": 1,
            "is_teacher": False,
            "journeys_completed": 0
        }

        db.table("user_profiles").insert(profile_data).execute()

        return AuthResponse(
            success=True,
            message="Account created successfully",
            access_token=auth_response.session.access_token if auth_response.session else None,
            refresh_token=auth_response.session.refresh_token if auth_response.session else None,
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        if "already registered" in error_message.lower() or "duplicate" in error_message.lower():
            raise HTTPException(status_code=400, detail="An account with this email already exists")
        raise HTTPException(status_code=500, detail=f"Signup failed: {error_message}")


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest, db: Client = Depends(get_supabase)):
    try:
        auth_response = db.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return AuthResponse(
            success=True,
            message="Signed in successfully",
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
            user_id=auth_response.user.id
        )

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        if "invalid" in error_message.lower() or "credentials" in error_message.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password")
        raise HTTPException(status_code=500, detail=f"Sign in failed: {error_message}")


@router.post("/signout")
async def signout(
    authorization: Optional[str] = Header(None),
    db: Client = Depends(get_supabase)
):
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No authorization token provided")
        db.auth.sign_out()
        return {"success": True, "message": "Signed out successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sign out failed: {str(e)}")


# ============================================================
# Profile Endpoints
# ============================================================

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        access_token = authorization.replace("Bearer ", "")
        user_data = verify_token(access_token)

        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = user_data["id"]

        response = db.table("user_profiles").select("*").eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = response.data[0]

        return UserProfileResponse(
            id=profile["id"],
            email=profile["email"],
            username=profile.get("username"),
            is_teacher=profile.get("is_teacher", False),
            housen_stage=profile.get("housen_stage", 1),
            housen_substage=profile.get("housen_substage", 1),
            journeys_completed=profile.get("journeys_completed", 0),
            created_at=profile.get("created_at", ""),
            updated_at=profile.get("updated_at", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    updates: UserProfileUpdate,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        access_token = authorization.replace("Bearer ", "")
        user_data = verify_token(access_token)

        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = user_data["id"]

        update_data = {}
        if updates.username is not None:
            update_data["username"] = updates.username

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        response = db.table("user_profiles").update(update_data).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = response.data[0]

        return UserProfileResponse(
            id=profile["id"],
            email=profile["email"],
            username=profile.get("username"),
            is_teacher=profile.get("is_teacher", False),
            housen_stage=profile.get("housen_stage", 1),
            housen_substage=profile.get("housen_substage", 1),
            journeys_completed=profile.get("journeys_completed", 0),
            created_at=profile.get("created_at", ""),
            updated_at=profile.get("updated_at", "")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        access_token = authorization.replace("Bearer ", "")
        user_data = verify_token(access_token)

        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = user_data["id"]

        profile_response = db.table("user_profiles").select("*").eq("id", user_id).execute()

        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = profile_response.data[0]

        stage_names = {
            1: "Accountive",
            2: "Constructive",
            3: "Classifying",
            4: "Interpretive",
            5: "Re-creative"
        }

        substage_names = {
            1: "Early",
            2: "Developing",
            3: "Advanced"
        }

        current_stage = profile.get("housen_stage", 1)
        current_substage = profile.get("housen_substage", 1)

        return UserStatsResponse(
            journeys_completed=profile.get("journeys_completed", 0),
            current_stage=current_stage,
            current_substage=current_substage,
            stage_name=stage_names.get(current_stage, "Accountive"),
            substage_name=substage_names.get(current_substage, "Early")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user stats: {str(e)}")


# ============================================================
# Refresh Token
# ============================================================

@router.post("/refresh")
async def refresh_token(
    body: dict,
    db: Client = Depends(get_supabase),
):
    refresh = body.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=400, detail="refresh_token is required.")

    try:
        response = db.auth.refresh_session(refresh)

        if not response.session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

        return {
            "success": True,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not refresh session. Please sign in again.")


# ============================================================
# Change Password
# ============================================================

@router.post("/change-password")
async def change_password(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")

    token = authorization.replace("Bearer ", "")
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    new_password = body.get("new_password")
    if not new_password or len(new_password) < 6:
        raise HTTPException(status_code=400, detail="new_password must be at least 6 characters.")

    try:
        db.auth.update_user({"password": new_password})
        return {"success": True, "message": "Password updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update password: {str(e)}")


# ============================================================
# Change Email
# ============================================================

@router.post("/change-email")
async def change_email(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")

    token = authorization.replace("Bearer ", "")
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    new_email = body.get("new_email")
    if not new_email:
        raise HTTPException(status_code=400, detail="new_email is required.")

    try:
        db.auth.update_user({"email": new_email})
        db.table("user_profiles").update({"email": new_email}).eq("id", user_data["id"]).execute()
        return {
            "success": True,
            "message": "Confirmation email sent to your new address. Please verify to complete the change.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update email: {str(e)}")


# ============================================================
# Delete Account
# ============================================================

@router.delete("/delete-account")
async def delete_account(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Permanently delete the current user's account.
    Required by Apple App Store and Google Play Store guidelines.
    Deleting the auth user cascades to user_profiles and all related tables.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header.")

    token = authorization.replace("Bearer ", "")
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user_id = user_data["id"]

    try:
        admin_client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
        admin_client.auth.admin.delete_user(user_id)

        return {
            "success": True,
            "message": "Your account has been permanently deleted.",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")