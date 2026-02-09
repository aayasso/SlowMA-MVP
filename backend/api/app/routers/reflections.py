"""
SlowMA Reflections Router
Generate reflection activities after a journey and assess user responses.
"""

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import (
    AssessmentScores,
    ReflectionActivitiesResponse,
    ReflectionAssessmentResponse,
    ReflectionSubmission,
)

router = APIRouter(prefix="/reflections", tags=["reflections"])

STAGE_NAMES = {1: "Accountive", 2: "Constructive", 3: "Classifying", 4: "Interpretive", 5: "Re-creative"}
SUBSTAGE_NAMES = {1: "Early", 2: "Developing", 3: "Advanced"}


def _get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


# ---------------------------------------------------------------------------
# Fallback activities when Anthropic API is unavailable
# ---------------------------------------------------------------------------

_FALLBACK_ACTIVITIES: dict[int, list[dict]] = {
    1: [
        {"id": "activity_1", "type": "connection", "title": "Personal Connection", "prompt": "What does this artwork remind you of from your own life?", "placeholder": "This reminds me of..."},
        {"id": "activity_2", "type": "text", "title": "Your Feelings", "prompt": "How did looking slowly at this artwork make you feel? Why?", "placeholder": "I felt..."},
    ],
    2: [
        {"id": "activity_1", "type": "text", "title": "Detailed Observation", "prompt": "Describe three details you noticed that you might have missed in a quick glance.", "placeholder": "I noticed..."},
        {"id": "activity_2", "type": "comparison", "title": "Compare and Contrast", "prompt": "Think of another artwork you know. How is this similar or different?", "placeholder": "Compared to..., this artwork..."},
    ],
    3: [
        {"id": "activity_1", "type": "text", "title": "Artist's Choices", "prompt": "What choices did the artist make, and why might they have made them?", "placeholder": "The artist chose to..."},
        {"id": "activity_2", "type": "synthesis", "title": "Connecting Ideas", "prompt": "How do your observations connect? What larger theme emerges?", "placeholder": "These observations connect because..."},
    ],
    4: [
        {"id": "activity_1", "type": "text", "title": "Multiple Meanings", "prompt": "What are two or three different interpretations? What evidence supports each?", "placeholder": "One interpretation could be..."},
        {"id": "activity_2", "type": "connection", "title": "Personal Significance", "prompt": "What does this artwork mean to you personally?", "placeholder": "This artwork speaks to me because..."},
    ],
    5: [
        {"id": "activity_1", "type": "synthesis", "title": "Deeper Questions", "prompt": "What questions does this artwork raise about art, life, or human experience?", "placeholder": "This artwork raises questions about..."},
        {"id": "activity_2", "type": "text", "title": "Your Looking Process", "prompt": "How did your understanding change during the slow looking? What surprised you?", "placeholder": "My understanding evolved..."},
    ],
}


# ---------------------------------------------------------------------------
# Keyword-based scoring helpers (mirrors user_assessment.py logic)
# ---------------------------------------------------------------------------

def _score_keywords(text: str, keywords: list[str], weight: float = 12.0) -> float:
    text_lower = text.lower()
    return min(100.0, sum(1 for k in keywords if k in text_lower) * weight)


def _assess_stage(text: str, stage: int, word_count: int) -> dict[str, float]:
    """Return growth-indicator scores for a single response."""
    t = text.lower()
    if stage == 1:
        return {
            "personal_connection": _score_keywords(t, ["i", "me", "my", "reminds me", "feel", "remember"], 15),
            "emotional_engagement": _score_keywords(t, ["feel", "emotion", "mood", "beautiful", "powerful", "moving"], 12),
            "storytelling": min(100, _score_keywords(t, ["story", "happening", "scene", "character"], 10) + min(50, word_count * 2)),
        }
    if stage == 2:
        return {
            "observational_detail": min(100, _score_keywords(t, ["notice", "see", "observe", "detail", "specific"], 8) + min(40, word_count * 1.5)),
            "descriptive_language": _score_keywords(t, ["color", "shape", "line", "texture", "bright", "dark"], 6),
            "pattern_recognition": _score_keywords(t, ["pattern", "repetition", "similar", "different", "compare"], 10),
        }
    if stage == 3:
        return {
            "analytical_thinking": _score_keywords(t, ["because", "why", "how", "analysis", "think", "reason"], 8),
            "technique_awareness": _score_keywords(t, ["technique", "method", "brush", "paint", "canvas"], 10),
            "interpretation_attempts": _score_keywords(t, ["means", "represents", "symbol", "meaning", "implies"], 8),
        }
    if stage == 4:
        return {
            "multiple_perspectives": _score_keywords(t, ["perspective", "viewpoint", "different", "another", "possible"], 7),
            "contextual_thinking": _score_keywords(t, ["context", "history", "period", "culture", "tradition"], 8),
            "sophisticated_analysis": min(100, _score_keywords(t, ["complex", "nuanced", "layered", "subtle"], 10) + min(50, word_count * 0.8)),
        }
    # stage 5
    return {
        "philosophical_thinking": _score_keywords(t, ["philosophy", "existential", "universal", "truth", "meaning"], 8),
        "metacognitive_awareness": _score_keywords(t, ["aware", "realize", "understand", "process", "reflection"], 7),
        "synthesis": min(100, _score_keywords(t, ["connect", "synthesize", "integrate", "relationship"], 8) + min(40, word_count * 0.6)),
    }


def _determine_progression(quality: float, stage: int, substage: int):
    if quality >= 75.0:
        if substage >= 3 and stage < 5:
            return stage + 1, 1, "progression"
        if substage < 3:
            return stage, substage + 1, "progression"
        return stage, substage, "maintenance"
    if quality <= 40.0:
        if substage > 1:
            return stage, substage - 1, "regression"
        if stage > 1:
            return stage - 1, 3, "regression"
        return stage, substage, "maintenance"
    return stage, substage, "maintenance"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{journey_id}/activities", response_model=ReflectionActivitiesResponse)
async def get_activities(
    journey_id: str,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Generate reflection activities for a completed journey.
    Uses the Anthropic API when available; falls back to stage-appropriate templates.
    """
    # Get journey data
    journey_result = db.table("journeys").select("*").eq("id", journey_id).eq("user_id", user["id"]).execute()
    if not journey_result.data:
        raise HTTPException(status_code=404, detail="Journey not found")

    row = journey_result.data[0]
    journey_data = json.loads(row.get("journey_data", "{}"))
    housen_stage = row.get("housen_stage", 1)
    housen_substage = row.get("housen_substage", 1)

    # Try Anthropic API for tailored activities
    api_key = os.getenv("ANTHROPIC_API_KEY")
    activities = None

    if api_key:
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            artwork_title = journey_data.get("artwork", {}).get("title", "this artwork")
            artist = journey_data.get("artwork", {}).get("artist", "the artist")

            prompt = (
                f"Create 2-4 reflection activities for a user at Housen Stage {housen_stage}.{housen_substage} "
                f"who just completed a slow-looking journey of '{artwork_title}' by {artist}. "
                "Return ONLY valid JSON: {\"activities\": [{\"id\": \"activity_1\", \"type\": \"text|comparison|connection|creative|synthesis\", "
                "\"title\": \"...\", \"prompt\": \"...\", \"placeholder\": \"...\"}]}"
            )

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3072,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            parsed = json.loads(raw.strip())
            activities = parsed.get("activities", [])
        except Exception:
            activities = None

    if not activities:
        activities = _FALLBACK_ACTIVITIES.get(housen_stage, _FALLBACK_ACTIVITIES[1])

    return ReflectionActivitiesResponse(journey_id=journey_id, activities=activities)


@router.post("/submit", response_model=ReflectionAssessmentResponse)
async def submit_reflection(
    body: ReflectionSubmission,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Submit reflection responses and receive an assessment.
    Updates the user's Housen stage/substage based on quality scores.
    """
    # Get user profile
    profile_result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    if not profile_result.data:
        raise HTTPException(status_code=404, detail="User profile not found")

    p = profile_result.data[0]
    stage = p.get("housen_stage", 1)
    substage = p.get("housen_substage", 1)

    # Score each response
    all_scores: list[AssessmentScores] = []
    flat_values: list[float] = []

    for activity_id, response_text in body.responses.items():
        if not response_text or len(response_text.strip()) < 10:
            continue
        word_count = len(response_text.split())
        scores = _assess_stage(response_text, stage, word_count)
        all_scores.append(AssessmentScores(activity_id=activity_id, scores=scores))
        flat_values.extend(scores.values())

    quality_score = (sum(flat_values) / len(flat_values)) if flat_values else 50.0
    stage_adj = {1: 1.0, 2: 0.95, 3: 0.90, 4: 0.85, 5: 0.80}
    quality_score = min(100.0, max(0.0, quality_score * stage_adj.get(stage, 1.0)))

    new_stage, new_substage, change = _determine_progression(quality_score, stage, substage)

    # Persist reflection
    reflection_row = {
        "id": f"{user['id']}_{body.journey_id}",
        "user_id": user["id"],
        "journey_id": body.journey_id,
        "responses": json.dumps(body.responses),
        "quality_score": quality_score,
        "change": change,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    db.table("reflections").upsert(reflection_row).execute()

    # Update user profile
    now = datetime.utcnow().isoformat()
    recent_scores = p.get("recent_quality_scores", [])[-9:]  # keep last 10
    recent_scores.append(quality_score)

    stage_history = p.get("stage_history", [])
    if change != "maintenance":
        stage_history.append({"date": now, "stage": f"{new_stage}.{new_substage}", "change": change})

    db.table("user_profiles").update({
        "housen_stage": new_stage,
        "housen_substage": new_substage,
        "recent_quality_scores": recent_scores,
        "stage_history": stage_history,
        "last_activity": now,
    }).eq("id", user["id"]).execute()

    # Generate feedback
    if change == "progression":
        feedback = f"Congratulations! You've advanced to Stage {new_stage}.{new_substage} ({STAGE_NAMES.get(new_stage, '')})."
    elif change == "regression":
        feedback = "Don't worry — learning isn't always linear. Take your time and focus on the fundamentals."
    else:
        feedback = "You're doing well at your current level. Keep practising and challenging yourself."

    return ReflectionAssessmentResponse(
        new_stage=new_stage,
        new_substage=new_substage,
        change=change,
        quality_score=round(quality_score, 1),
        scores=all_scores,
        feedback=feedback,
        stage_name=STAGE_NAMES.get(new_stage, "Unknown"),
        substage_name=SUBSTAGE_NAMES.get(new_substage, "Unknown"),
    )
