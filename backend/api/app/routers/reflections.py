"""
SlowMA Reflections Router
Handles reflection activities and assessment after journeys.
NOW WITH AI-POWERED ACTIVITY GENERATION!
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List
from app.database import get_supabase, verify_token, Client
from app.models.schemas import (
    ReflectionActivitiesResponse,
    ReflectionActivity,
    ReflectionSubmission,
    ReflectionAssessmentResponse,
    ActivityType,
    ProgressionChange
)
from app.activity_generator import get_activity_generator

router = APIRouter(prefix="/api/reflections", tags=["Reflections"])


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

@router.get("/{journey_id}/activities", response_model=ReflectionActivitiesResponse)
async def get_activities(
    journey_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Get AI-generated reflection activities for a completed journey.
    
    This is called after the user finishes the observation walkthrough.
    Returns 3 personalized activities tailored to their Housen stage.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Path Parameters:
    - journey_id: UUID of the completed journey
    
    Returns:
    - List of 3 AI-generated reflection activities
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Get journey
        journey_response = db.table("journeys").select("*").eq(
            "id", journey_id
        ).eq("user_id", user_id).execute()
        
        if not journey_response.data:
            raise HTTPException(
                status_code=404,
                detail="Journey not found"
            )
        
        journey = journey_response.data[0]
        housen_stage = journey.get("housen_stage", 1)
        housen_substage = journey.get("housen_substage", 1)
        at_museum = journey.get("at_museum", False)
        
        # Get activity generator
        generator = get_activity_generator()
        
        # Generate activities using AI
        activities = generator.generate_activities(
            housen_stage=housen_stage,
            housen_substage=housen_substage,
            at_museum=at_museum,
            artwork_context=None  # Will add artwork details later
        )
        
        return ReflectionActivitiesResponse(
            journey_id=journey_id,
            activities=activities
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get activities: {str(e)}"
        )


@router.post("/submit", response_model=ReflectionAssessmentResponse)
async def submit_reflection(
    submission: ReflectionSubmission,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase)
):
    """
    Submit reflection responses and get assessment.
    
    This analyzes the user's responses and determines:
    - Current Housen stage and substage
    - Whether they've progressed, regressed, or maintained
    - Quality score for the reflection
    - Personalized feedback
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Request Body:
    - journey_id: UUID of the journey
    - responses: Dictionary mapping activity_id to response text
    
    Returns:
    - Assessment with new stage, feedback, and scores
    """
    try:
        # Verify user
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]
        
        # Verify journey exists and belongs to user
        journey_response = db.table("journeys").select("*").eq(
            "id", submission.journey_id
        ).eq("user_id", user_id).execute()
        
        if not journey_response.data:
            raise HTTPException(
                status_code=404,
                detail="Journey not found"
            )
        
        journey = journey_response.data[0]
        
        # Get current user profile
        profile_response = db.table("user_profiles").select(
            "housen_stage, housen_substage"
        ).eq("id", user_id).execute()
        
        if not profile_response.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )
        
        profile = profile_response.data[0]
        current_stage = profile["housen_stage"]
        current_substage = profile["housen_substage"]
        
        # For MVP: Simple assessment logic
        # Later: This will use AI to analyze responses
        
        # Calculate simple quality score based on response length and depth
        total_length = sum(len(response) for response in submission.responses.values())
        num_responses = len(submission.responses)
        
        # Average response length (good = 100+ chars per response)
        avg_length = total_length / num_responses if num_responses > 0 else 0
        quality_score = min(1.0, avg_length / 100)
        
        # Simple progression logic for MVP
        # If quality score > 0.7, might progress substage
        new_stage = current_stage
        new_substage = current_substage
        change = ProgressionChange.MAINTENANCE
        
        if quality_score > 0.7 and current_substage < 3:
            new_substage = current_substage + 1
            change = ProgressionChange.PROGRESSION
        elif quality_score > 0.9 and current_substage == 3 and current_stage < 5:
            new_stage = current_stage + 1
            new_substage = 1
            change = ProgressionChange.PROGRESSION
        
        # Update user profile if progressed
        if change == ProgressionChange.PROGRESSION:
            db.table("user_profiles").update({
                "housen_stage": new_stage,
                "housen_substage": new_substage
            }).eq("id", user_id).execute()
        
        # Store reflection in database
        reflection_data = {
            "journey_id": submission.journey_id,
            "user_id": user_id,
            "responses": submission.responses,
            "quality_score": quality_score,
            "housen_stage_after": new_stage,
            "housen_substage_after": new_substage
        }
        
        db.table("reflections").insert(reflection_data).execute()
        
        # Stage names for response
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
        
        # Generate feedback
        if change == ProgressionChange.PROGRESSION:
            feedback = f"Excellent work! Your thoughtful observations show growth in visual literacy. You've progressed to {stage_names[new_stage]} - {substage_names[new_substage]}."
        else:
            feedback = f"Great reflection! You're developing your observation skills at the {stage_names[new_stage]} - {substage_names[new_substage]} level. Keep practicing slow looking."
        
        return ReflectionAssessmentResponse(
            new_stage=new_stage,
            new_substage=new_substage,
            change=change,
            quality_score=quality_score,
            scores=[],  # Will be populated with detailed scores later
            feedback=feedback,
            stage_name=stage_names[new_stage],
            substage_name=substage_names[new_substage]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit reflection: {str(e)}"
        )