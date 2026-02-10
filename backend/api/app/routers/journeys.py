"""
SlowMA Journeys Router
Handles journey creation, retrieval, and completion.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from datetime import datetime
from app.database import get_supabase, verify_token, Client
from app.models.schemas import (
    JourneyCreate,
    JourneyResponse,
    JourneyListItem,
    JourneyCompleteRequest,
    ArtworkInfo
)

router = APIRouter(prefix="/api/journeys", tags=["Journeys"])


# ============================================================
# Helper Functions
# ============================================================

def get_user_from_token(authorization: str) -> dict:
    """Extract and verify user from authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
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
    
    return user_data


# ============================================================
# Endpoints
# ============================================================

@router.post("/", response_model=JourneyResponse)
async def create_journey(
    request: JourneyCreate,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Create a new journey for an artwork.
    
    This is called when:
    - User taps "Start Journey" on a seed artwork
    - User uploads their own photo of an artwork
    
    For MVP, we'll create a simple journey structure.
    Later, this will call AI to generate personalized steps.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Request Body:
    - image_filename: Filename of the artwork
    - at_museum: Whether user is physically at a museum
    
    Returns:
    - Complete journey with steps and prompts
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Get user's current Housen stage for personalization
        profile_response = db.table("user_profiles").select(
            "housen_stage, housen_substage"
        ).eq("id", user_id).execute()
        
        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        profile = profile_response.data[0]
        housen_stage = profile.get("housen_stage", 1)
        housen_substage = profile.get("housen_substage", 1)
        
        # For MVP: Create a simple journey structure
        # Later: This will be AI-generated based on artwork and user stage
        
        journey_data = {
            "user_id": user_id,
            "image_filename": request.image_filename,
            "at_museum": request.at_museum,
            "housen_stage": housen_stage,
            "housen_substage": housen_substage,
            "total_steps": 4,  # Simple 4-step journey for MVP
            "estimated_duration_minutes": 5,
            "completed": False
        }
        
        # Insert journey
        journey_response = db.table("journeys").insert(journey_data).execute()
        
        if not journey_response.data:
            raise HTTPException(
                status_code=500,
                detail="Failed to create journey"
            )
        
        journey = journey_response.data[0]
        journey_id = journey["id"]
        
        # Return journey response
        # For MVP, we'll return a simple structure
        # Later, this will include AI-generated steps and prompts
        
        return JourneyResponse(
            journey_id=journey_id,
            artwork=ArtworkInfo(
                title="Untitled",
                artist="Unknown",
                year=None,
                period=None,
                style=None
            ),
            total_steps=4,
            estimated_duration_minutes=5,
            steps=[],  # Will be populated by AI generator later
            welcome_text="Take your time observing this artwork. Let your eyes wander naturally.",
            final_summary={
                "main_takeaway": "You've completed your observation journey.",
                "connections": "Notice what stood out to you most.",
                "invitation_to_return": "Come back and see what new details you discover.",
                "reflection_question": "What did you notice that surprised you?"
            },
            housen_stage=housen_stage,
            housen_substage=housen_substage,
            at_museum=request.at_museum,
            image_filename=request.image_filename,
            created_at=journey.get("created_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create journey: {str(e)}"
        )


@router.get("/", response_model=List[JourneyListItem])
async def list_journeys(
    completed: Optional[bool] = None,
    limit: int = 20,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Get all journeys for the current user.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Query Parameters:
    - completed: Filter by completion status (optional)
    - limit: Maximum number of journeys to return (default 20)
    
    Returns:
    - List of journey summaries
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Build query
        query = db.table("journeys").select("*").eq("user_id", user_id)
        
        # Apply filters
        if completed is not None:
            query = query.eq("completed", completed)
        
        # Execute query
        response = query.order("created_at", desc=True).limit(limit).execute()
        
        if not response.data:
            return []
        
        # Transform to list items
        journeys = []
        for journey in response.data:
            journeys.append(JourneyListItem(
                journey_id=journey["id"],
                artwork=ArtworkInfo(
                    title="Untitled",  # Will be populated from artwork data later
                    artist="Unknown",
                    year=None,
                    period=None,
                    style=None
                ),
                total_steps=journey.get("total_steps", 4),
                estimated_duration_minutes=journey.get("estimated_duration_minutes", 5),
                housen_stage=journey.get("housen_stage", 1),
                completed_at=journey.get("completed_at"),
                image_filename=journey.get("image_filename")
            ))
        
        return journeys
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list journeys: {str(e)}"
        )


@router.get("/{journey_id}", response_model=JourneyResponse)
async def get_journey(
    journey_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Get a specific journey by ID.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Path Parameters:
    - journey_id: UUID of the journey
    
    Returns:
    - Complete journey details
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Get journey
        response = db.table("journeys").select("*").eq(
            "id", journey_id
        ).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Journey not found"
            )
        
        journey = response.data[0]
        
        # Return journey response
        return JourneyResponse(
            journey_id=journey["id"],
            artwork=ArtworkInfo(
                title="Untitled",
                artist="Unknown",
                year=None,
                period=None,
                style=None
            ),
            total_steps=journey.get("total_steps", 4),
            estimated_duration_minutes=journey.get("estimated_duration_minutes", 5),
            steps=[],  # Will be populated later
            welcome_text="Take your time observing this artwork.",
            final_summary={
                "main_takeaway": "You've completed your observation journey.",
                "connections": "Notice what stood out to you most.",
                "invitation_to_return": "Come back and see what new details you discover.",
                "reflection_question": "What did you notice that surprised you?"
            },
            housen_stage=journey.get("housen_stage", 1),
            housen_substage=journey.get("housen_substage", 1),
            at_museum=journey.get("at_museum", False),
            image_filename=journey.get("image_filename"),
            created_at=journey.get("created_at"),
            completed_at=journey.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get journey: {str(e)}"
        )


@router.post("/{journey_id}/complete")
async def complete_journey(
    journey_id: str,
    request: JourneyCompleteRequest,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Mark a journey as completed.
    
    This is called when the user finishes walking through all steps.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Path Parameters:
    - journey_id: UUID of the journey
    
    Request Body:
    - completion_time_seconds: How long the journey took
    - steps_viewed: Number of steps the user viewed
    
    Returns:
    - Success message
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Verify journey exists and belongs to user
        journey_response = db.table("journeys").select("*").eq(
            "id", journey_id
        ).eq("user_id", user_id).execute()
        
        if not journey_response.data:
            raise HTTPException(
                status_code=404,
                detail="Journey not found"
            )
        
        journey = journey_response.data[0]
        
        if journey.get("completed"):
            raise HTTPException(
                status_code=400,
                detail="Journey already completed"
            )
        
        # Update journey as completed
        update_data = {
            "completed": True,
            "completed_at": datetime.utcnow().isoformat(),
            "completion_time_seconds": request.completion_time_seconds
        }
        
        db.table("journeys").update(update_data).eq("id", journey_id).execute()
        
        # Update user's journey count
        db.table("user_profiles").update({
            "journeys_completed": db.table("user_profiles").select(
                "journeys_completed"
            ).eq("id", user_id).execute().data[0]["journeys_completed"] + 1
        }).eq("id", user_id).execute()
        
        return {
            "success": True,
            "message": "Journey completed successfully",
            "journey_id": journey_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete journey: {str(e)}"
        )