"""
SlowMA Reflections Router
Handles reflection activities and assessment after journeys.

- GET  /{journey_id}/activities  → returns 3 AI-generated activities
- POST /submit                   → saves rich behavioral data, runs AI Housen assessment,
                                   logs stage changes to stage_history
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from anthropic import Anthropic
from fastapi import APIRouter, Depends, Header, HTTPException

from app.activity_generator import get_activity_generator
from app.cost_logger import tracked_completion
from app.database import Client, get_supabase, verify_token
from app.models.schemas import (
    AssessmentScores,
    ProgressionChange,
    ReflectionActivitiesResponse,
    ReflectionAssessmentResponse,
    ReflectionSubmission,
)

router = APIRouter(prefix="/api/reflections", tags=["Reflections"])

ASSESSMENT_MODEL_VERSION = "1.0"
MODEL = "claude-sonnet-4-20250514"

STAGE_NAMES = {
    1: "Accountive",
    2: "Constructive",
    3: "Classifying",
    4: "Interpretive",
    5: "Re-creative",
}

SUBSTAGE_NAMES = {
    1: "Early",
    2: "Developing",
    3: "Advanced",
}


# ============================================================
# Helpers
# ============================================================

def get_user_from_token(authorization: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.replace("Bearer ", "")
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_data


def count_words(text: Optional[str]) -> int:
    if not text:
        return 0
    return len(text.split())


def count_chars(text: Optional[str]) -> int:
    if not text:
        return 0
    return len(text.strip())


def get_anthropic_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return Anthropic(api_key=api_key)


def normalize_change(raw: str) -> str:
    val = (raw or "maintenance").lower().strip()
    if val in ("progression", "advancement", "advance", "advanced", "progress", "progressed"):
        return "progression"
    elif val in ("regression", "regress", "regressed", "decline", "declined"):
        return "regression"
    else:
        return "maintenance"


# ============================================================
# AI Housen Assessment
# ============================================================

def run_housen_assessment(
    responses: list,
    current_stage: int,
    current_substage: int,
    artwork_context: Optional[dict] = None,
    user_id: Optional[str] = None,
    journey_id: Optional[str] = None,
) -> dict:
    response_summary = []
    for r in responses:
        text = r.response_text or ""
        if r.audio_transcript:
            text = f"[Voice transcript] {r.audio_transcript}"
        elif r.response_data:
            text = f"[Structured response] {json.dumps(r.response_data)}"
        response_summary.append(f"Activity ({r.activity_type.value}): {text}")

    artwork_desc = "an unidentified artwork"
    if artwork_context:
        parts = []
        if artwork_context.get("title"):
            parts.append(artwork_context["title"])
        if artwork_context.get("artist"):
            parts.append(f"by {artwork_context['artist']}")
        if parts:
            artwork_desc = " ".join(parts)

    prompt = f"""You are an expert assessor trained in Abigail Housen's five stages of aesthetic development.

A user just completed slow looking activities for {artwork_desc}.
Their current Housen stage is {current_stage}.{current_substage} ({STAGE_NAMES[current_stage]} — {SUBSTAGE_NAMES[current_substage]}).

USER RESPONSES:
{chr(10).join(response_summary)}

HOUSEN STAGES:
1 (Accountive): Personal stories, emotions, concrete observations, judgmental language
2 (Constructive): Building perceptions, using senses, comparing to own world, simple narratives
3 (Classifying): Analytical, art historical knowledge, categorizing, interpreting with evidence
4 (Interpretive): Personal encounter balanced with analysis, multiple interpretations, symbolic meanings
5 (Re-creative): Synthesis, universal questions, metacognitive awareness, empathy with artist

SUBSTAGES (within each stage):
.1 Early — just entering, needs support, inconsistent demonstration
.2 Developing — building confidence, more consistent
.3 Advanced — mastering this stage, ready to be stretched toward next

GROWTH INDICATORS to look for:
- Quantity: How many distinct observations or ideas
- Quality: Specificity, accuracy, and depth
- Complexity: Recognition of patterns, relationships, ambiguity
- Evidence: Using observations to support interpretations
- Flexibility: Considering multiple perspectives
- Transfer: Applying this way of seeing to broader contexts

ASSESSMENT TASK:
Based on the responses, determine:
1. Whether the user should progress, maintain, or regress
2. Which growth indicators were demonstrated
3. A confidence score for your assessment (0.0 to 1.0)
4. Brief encouraging feedback for the user (1-2 sentences, warm tone)

Be generous but honest. Early stage users showing ANY evidence of meaning-making deserve recognition.
Do not penalize users for short responses to structured activities (word clouds, sorting, etc.).

IMPORTANT: For the "change" field you MUST use exactly one of these three words:
- "progression" (user shows evidence of growth)
- "maintenance" (user is performing solidly at current level)
- "regression" (user responses are significantly below current level)

Return ONLY valid JSON — no explanation, no markdown:
{{
    "new_stage": {current_stage},
    "new_substage": {current_substage},
    "change": "maintenance",
    "quality_score": 0.0,
    "indicators_demonstrated": [],
    "assessment_confidence": 0.0,
    "advancement_recommended": false,
    "feedback": "Your feedback here.",
    "reasoning": "Internal reasoning (not shown to user, max 300 chars)"
}}"""

    try:
        client = get_anthropic_client()
        message = tracked_completion(
            client=client,
            feature="housen_assessment",
            model=MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            journey_id=journey_id,
            housen_stage=current_stage,
        )

        raw = message.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        result["new_stage"] = max(1, min(5, int(result.get("new_stage", current_stage))))
        result["new_substage"] = max(1, min(3, int(result.get("new_substage", current_substage))))
        result["quality_score"] = max(0.0, min(1.0, float(result.get("quality_score", 0.5))))
        result["assessment_confidence"] = max(0.0, min(1.0, float(result.get("assessment_confidence", 0.5))))
        result["change"] = normalize_change(result.get("change", "maintenance"))

        return result

    except Exception as e:
        print(f"AI assessment failed, using fallback: {e}")
        return _fallback_assessment(responses, current_stage, current_substage)


def _fallback_assessment(responses, current_stage, current_substage):
    total_chars = sum(
        count_chars(r.response_text or (r.audio_transcript or ""))
        for r in responses
    )
    avg_chars = total_chars / len(responses) if responses else 0
    quality_score = min(1.0, avg_chars / 150)

    new_stage = current_stage
    new_substage = current_substage
    change = "maintenance"

    if quality_score > 0.6 and current_substage < 3:
        new_substage = current_substage + 1
        change = "progression"
    elif quality_score > 0.8 and current_substage == 3 and current_stage < 5:
        new_stage = current_stage + 1
        new_substage = 1
        change = "progression"

    return {
        "new_stage": new_stage,
        "new_substage": new_substage,
        "change": change,
        "quality_score": quality_score,
        "indicators_demonstrated": [],
        "assessment_confidence": 0.3,
        "advancement_recommended": change == "progression",
        "feedback": f"Great reflection! Keep practicing slow looking at the {STAGE_NAMES[new_stage]} level.",
        "reasoning": "Fallback assessment based on response length.",
    }


# ============================================================
# Stage History Logging
# ============================================================

def log_stage_change(
    db: Client,
    user_id: str,
    stage_before: int,
    substage_before: int,
    stage_after: int,
    substage_after: int,
    change_type: str,
    journey_id: str,
    journey_number: int,
    quality_score: float,
    indicators: list,
    confidence: float,
    artwork_id: Optional[str],
    assignment_id: Optional[str],
    classroom_id: Optional[str],
):
    try:
        journeys_at_stage_resp = db.table("stage_history").select(
            "id", count="exact"
        ).eq("user_id", user_id).eq("stage_before", stage_before).execute()
        journeys_at_stage = journeys_at_stage_resp.count or 0

        first_entry_resp = db.table("stage_history").select(
            "created_at"
        ).eq("user_id", user_id).eq("stage_after", stage_before).order(
            "created_at", desc=False
        ).limit(1).execute()

        days_at_stage = None
        if first_entry_resp.data:
            first_entry = datetime.fromisoformat(
                first_entry_resp.data[0]["created_at"].replace("Z", "+00:00")
            )
            days_at_stage = (datetime.now(timezone.utc) - first_entry).days

        history_record = {
            "user_id": user_id,
            "stage_before": stage_before,
            "substage_before": substage_before,
            "stage_after": stage_after,
            "substage_after": substage_after,
            "stage": stage_after,
            "substage": substage_after,
            "change_type": change_type,
            "related_journey_id": journey_id,
            "journey_number": journey_number,
            "journeys_at_stage": journeys_at_stage,
            "days_at_stage": days_at_stage,
            "quality_score": quality_score,
            "indicators_observed": indicators,
            "assessment_confidence": confidence,
            "artwork_id": artwork_id,
            "assignment_id": assignment_id,
            "classroom_id": classroom_id,
        }

        db.table("stage_history").insert(history_record).execute()
        print(f"Stage history logged: {stage_before}.{substage_before} → {stage_after}.{substage_after} ({change_type})")

    except Exception as e:
        print(f"Warning: failed to log stage history: {e}")


# ============================================================
# Endpoints
# ============================================================

@router.get("/{journey_id}/activities", response_model=ReflectionActivitiesResponse)
async def get_activities(
    journey_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    try:
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]

        journey_resp = db.table("journeys").select("*").eq(
            "id", journey_id
        ).eq("user_id", user_id).execute()
        if not journey_resp.data:
            raise HTTPException(status_code=404, detail="Journey not found")

        journey = journey_resp.data[0]
        housen_stage = journey.get("housen_stage_at_time") or journey.get("housen_stage", 1)
        housen_substage = journey.get("housen_substage_at_time") or journey.get("housen_substage", 1)
        at_museum = journey.get("at_museum", False)

        artwork_context = {
            "title": journey.get("artwork_title"),
            "artist": journey.get("artwork_artist"),
            "style": journey.get("artwork_style"),
        }

        generator = get_activity_generator()
        activities = generator.generate_activities(
            housen_stage=housen_stage,
            housen_substage=housen_substage,
            at_museum=at_museum,
            artwork_context=artwork_context,
            user_id=user_id,
            journey_id=journey_id,
        )

        return ReflectionActivitiesResponse(
            journey_id=journey_id,
            activities=activities,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get activities: {str(e)}")


@router.post("/submit", response_model=ReflectionAssessmentResponse)
async def submit_reflection(
    submission: ReflectionSubmission,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    try:
        user_data = get_user_from_token(authorization)
        user_id = user_data["id"]

        journey_resp = db.table("journeys").select("*").eq(
            "id", submission.journey_id
        ).eq("user_id", user_id).execute()

        if not journey_resp.data:
            raise HTTPException(status_code=404, detail="Journey not found")
        journey = journey_resp.data[0]

        profile_resp = db.table("user_profiles").select(
            "housen_stage, housen_substage, journeys_completed, school_id"
        ).eq("id", user_id).execute()

        if not profile_resp.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        profile = profile_resp.data[0]

        current_stage = profile["housen_stage"] or 1
        current_substage = profile["housen_substage"] or 1
        journeys_completed = profile.get("journeys_completed") or 0

        artwork_context = {
            "title": journey.get("artwork_title"),
            "artist": journey.get("artwork_artist"),
            "style": journey.get("artwork_style"),
        }

        assessment = run_housen_assessment(
            responses=submission.responses,
            current_stage=current_stage,
            current_substage=current_substage,
            artwork_context=artwork_context,
            user_id=user_id,
            journey_id=submission.journey_id,
        )

        new_stage = assessment["new_stage"]
        new_substage = assessment["new_substage"]
        change_str = assessment["change"]
        quality_score = assessment["quality_score"]
        indicators = assessment.get("indicators_demonstrated", [])
        confidence = assessment.get("assessment_confidence", 0.5)
        advancement_recommended = assessment.get("advancement_recommended", False)
        feedback = assessment.get("feedback", "")

        if change_str == "progression":
            change = ProgressionChange.PROGRESSION
        elif change_str == "regression":
            change = ProgressionChange.REGRESSION
        else:
            change = ProgressionChange.MAINTENANCE

        if change in (ProgressionChange.PROGRESSION, ProgressionChange.REGRESSION):
            db.table("user_profiles").update({
                "housen_stage": new_stage,
                "housen_substage": new_substage,
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }).eq("id", user_id).execute()

            log_stage_change(
                db=db,
                user_id=user_id,
                stage_before=current_stage,
                substage_before=current_substage,
                stage_after=new_stage,
                substage_after=new_substage,
                change_type=change_str,
                journey_id=submission.journey_id,
                journey_number=journeys_completed + 1,
                quality_score=quality_score,
                indicators=indicators,
                confidence=confidence,
                artwork_id=journey.get("artwork_id"),
                assignment_id=journey.get("assignment_id"),
                classroom_id=journey.get("classroom_id"),
            )

        for idx, response in enumerate(submission.responses):
            response_text = response.response_text or response.audio_transcript or ""
            word_count = response.word_count if response.word_count is not None else count_words(response_text)
            char_count = response.character_count if response.character_count is not None else count_chars(response_text)

            reflection_record = {
                "journey_id": submission.journey_id,
                "user_id": user_id,
                "artwork_id": journey.get("artwork_id"),
                "assignment_id": journey.get("assignment_id"),
                "classroom_id": journey.get("classroom_id"),
                "journey_number": journeys_completed + 1,
                "artwork_is_seed": journey.get("artwork_is_seed", False),
                "is_teacher_assigned": journey.get("assignment_id") is not None,
                "stage_before": current_stage,
                "substage_before": current_substage,
                "stage_after": new_stage,
                "substage_after": new_substage,
                "change_type": change_str,
                "activities_presented": submission.activities_presented,
                "activity_type": response.activity_type.value,
                "activity_index": idx + 1,
                "responses": {
                    "text": response.response_text,
                    "data": response.response_data,
                },
                "response_modality": response.response_modality,
                "word_count": word_count,
                "character_count": char_count,
                "time_to_first_input_seconds": response.time_to_first_input_seconds,
                "total_time_seconds": response.total_time_seconds,
                "revision_count": response.revision_count,
                "session_started_at": submission.session_started_at,
                "session_submitted_at": submission.session_submitted_at,
                "audio_duration_seconds": response.audio_duration_seconds,
                "audio_transcript": response.audio_transcript,
                "audio_pause_count": response.audio_pause_count,
                "quality_score": quality_score,
                "indicators_demonstrated": indicators,
                "feedback": feedback,
                "ai_assessment_raw": assessment,
                "assessment_confidence": confidence,
                "advancement_recommended": advancement_recommended,
                "assessment_model_version": ASSESSMENT_MODEL_VERSION,
            }

            db.table("reflections").insert(reflection_record).execute()

        db.table("user_profiles").update({
            "journeys_completed": journeys_completed + 1,
        }).eq("id", user_id).execute()

        return ReflectionAssessmentResponse(
            new_stage=new_stage,
            new_substage=new_substage,
            change=change,
            quality_score=quality_score,
            scores=[],
            feedback=feedback,
            stage_name=STAGE_NAMES[new_stage],
            substage_name=SUBSTAGE_NAMES[new_substage],
            indicators_demonstrated=indicators,
            assessment_confidence=confidence,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit reflection: {str(e)}")