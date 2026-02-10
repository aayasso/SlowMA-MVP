"""
SlowMA Users Router
Handles user authentication and profile management.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
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
    """
    Create a new user account.
    
    Request Body:
    - email: User's email address
    - password: Password (minimum 6 characters)
    - username: Optional display name
    
    Returns:
    - AuthResponse with access_token and user_id
    """
    try:
        # Create user with Supabase Auth
        auth_response = db.auth.sign_up({
            "email": request.email,
            "password": request.password,
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=400,
                detail="Failed to create user account"
            )
        
        user_id = auth_response.user.id
        
        # Create user profile in database
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
        
    except Exception as e:
        error_message = str(e)
        
        # Handle duplicate email
        if "already registered" in error_message.lower() or "duplicate" in error_message.lower():
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists"
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Signup failed: {error_message}"
        )


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest, db: Client = Depends(get_supabase)):
    """
    Sign in to an existing account.
    
    Request Body:
    - email: User's email address
    - password: User's password
    
    Returns:
    - AuthResponse with access_token and user_id
    """
    try:
        # Sign in with Supabase Auth
        auth_response = db.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not auth_response.user or not auth_response.session:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
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
        
        # Handle invalid credentials
        if "invalid" in error_message.lower() or "credentials" in error_message.lower():
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Sign in failed: {error_message}"
        )


@router.post("/signout")
async def signout(
    authorization: Optional[str] = Header(None),
    db: Client = Depends(get_supabase)
):
    """
    Sign out the current user.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Returns:
    - Success message
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="No authorization token provided"
            )
        
        access_token = authorization.replace("Bearer ", "")
        
        # Sign out with Supabase
        db.auth.sign_out()
        
        return {
            "success": True,
            "message": "Signed out successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sign out failed: {str(e)}"
        )


# ============================================================
# Profile Endpoints
# ============================================================

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Get the current user's profile.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Returns:
    - Full user profile with stats
    """
    try:
        # Extract token
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header"
            )
        
        access_token = authorization.replace("Bearer ", "")
        
        # Verify token and get user
        user_data = verify_token(access_token)
        if not user_data:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        user_id = user_data["id"]
        
        # Get profile from database
        response = db.table("user_profiles").select("*").eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    updates: UserProfileUpdate,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Update the current user's profile.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Request Body:
    - username: New display name (optional)
    
    Returns:
    - Updated user profile
    """
    try:
        # Extract and verify token
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header"
            )
        
        access_token = authorization.replace("Bearer ", "")
        user_data = verify_token(access_token)
        
        if not user_data:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        user_id = user_data["id"]
        
        # Build update data
        update_data = {}
        if updates.username is not None:
            update_data["username"] = updates.username
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields to update"
            )
        
        # Update profile
        response = db.table("user_profiles").update(
            update_data
        ).eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Get the current user's learning statistics.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Returns:
    - User stats including journey count and Housen stage info
    """
    try:
        # Verify token
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        access_token = authorization.replace("Bearer ", "")
        user_data = verify_token(access_token)
        
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user_id = user_data["id"]
        
        # Get profile
        profile_response = db.table("user_profiles").select("*").eq("id", user_id).execute()
        
        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        profile = profile_response.data[0]
        
        # Map stage numbers to names
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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user stats: {str(e)}"
        )