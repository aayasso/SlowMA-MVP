"""
SlowMA Reflections Router
Handles reflection activities and assessment after journeys.
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


def generate_simple_activities(housen_stage: int) -> List[ReflectionActivity]:
    """
    Generate simple reflection activities based on user's Housen stage.
    
    For MVP, this creates basic activities.
    Later, this will be AI-generated and personalized.
    """
    
    # Stage 1 (Accountive): Simple, concrete observations
    if housen_stage == 1:
        activities = [
            ReflectionActivity(
                id="activity_1",
                type=ActivityType.TEXT,
                title="What did you see?",
                prompt="Describe what you noticed in the artwork.",
                placeholder="I saw colors, shapes, objects...",
                why_this_activity="This helps you practice detailed observation."
            ),
            ReflectionActivity(
                id="activity_2",
                type=ActivityType.TEXT,
                title="Colors and shapes",
                prompt="What colors or shapes stood out to you?",
                placeholder="The blue in the corner, the round shape...",
                why_this_activity="Focusing on elements builds visual literacy."
            ),
            ReflectionActivity(
                id="activity_3",
                type=ActivityType.TEXT,
                title="Your feeling",
                prompt="How did this artwork make you feel?",
                placeholder="It made me feel calm, excited, curious...",
                why_this_activity="Connecting emotions to art deepens engagement."
            )
        ]
    
    # Stage 2 (Constructive): Building interpretations
    elif housen_stage == 2:
        activities = [
            ReflectionActivity(
                id="activity_1",
                type=ActivityType.TEXT,
                title="Tell the story",
                prompt="What story might this artwork be telling?",
                placeholder="I think this shows...",
                why_this_activity="Narrative thinking develops interpretation skills."
            ),
            ReflectionActivity(
                id="activity_2",
                type=ActivityType.CONNECTION,
                title="Connect to your life",
                prompt="Does this remind you of anything from your own experience?",
                placeholder="This reminds me of...",
                why_this_activity="Personal connections make art more meaningful."
            ),
            ReflectionActivity(
                id="activity_3",
                type=ActivityType.TEXT,
                title="Artist's choices",
                prompt="Why do you think the artist made these choices?",
                placeholder="The artist might have wanted to...",
                why_this_activity="Considering intent builds critical thinking."
            )
        ]
    
    # Stage 3+ (Classifying and beyond): More analytical
    else:
        activities = [
            ReflectionActivity(
                id="activity_1",
                type=ActivityType.TEXT,
                title="Analyze the composition",
                prompt="How do the elements work together in this piece?",
                placeholder="The composition uses...",
                why_this_activity="Analyzing structure deepens understanding."
            ),
            ReflectionActivity(
                id="activity_2",
                type=ActivityType.COMPARISON,
                title="Compare and contrast",
                prompt="How is this similar to or different from other artworks you've seen?",
                placeholder="Compared to other works, this...",
                why_this_activity="Comparison builds analytical frameworks."
            ),
            ReflectionActivity(
                id="activity_3",
                type=ActivityType.SYNTHESIS,
                title="Synthesize your thoughts",
                prompt="What new understanding did you gain from this observation?",
                placeholder="I now understand that...",
                why_this_activity="Synthesis consolidates learning."
            )
        ]
    
    return activities


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
    Get reflection activities for a completed journey.
    
    This is called after the user finishes the observation walkthrough.
    Returns 3 activities tailored to their Housen stage.
    
    Headers:
    - Authorization: Bearer {access_token}
    
    Path Parameters:
    - journey_id: UUID of the completed journey
    
    Returns:
    - List of 3 reflection activities
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
        
        # Generate activities based on stage
        activities = generate_simple_activities(housen_stage)
        
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
        
        # Calculate simple quality score based on response length
        total_length = sum(len(response) for response in submission.responses.values())
        quality_score = min(1.0, total_length / 300)  # 300 chars = perfect score
        
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