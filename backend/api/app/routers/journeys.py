"""
SlowMA Journeys Router
Create, retrieve, and complete slow-looking journeys.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import (
    JourneyCompleteRequest,
    JourneyCreate,
    JourneyListItem,
    JourneyResponse,
)

router = APIRouter(prefix="/journeys", tags=["journeys"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))


def _get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=JourneyResponse, status_code=status.HTTP_201_CREATED)
async def create_journey(
    body: JourneyCreate,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Generate a new slow-looking journey from an uploaded artwork image.
    Calls the Anthropic Claude API to analyse the image and produce a
    step-by-step guided observation sequence tailored to the user's
    current Housen stage.
    """
    from anthropic import Anthropic
    import base64
    import hashlib

    # Fetch user profile for Housen stage
    profile_result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    if not profile_result.data:
        raise HTTPException(status_code=404, detail="User profile not found")

    profile = profile_result.data[0]
    housen_stage = profile.get("housen_stage", 1)
    housen_substage = profile.get("housen_substage", 1)

    # Locate the image file
    image_path = UPLOAD_DIR / body.image_filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image file not found: {body.image_filename}")

    # Check cache
    cache_dir = Path("data/journey_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    image_hash = hashlib.md5(image_path.read_bytes()).hexdigest()
    cache_key = f"{image_hash}_s{housen_stage}_{housen_substage}"
    cache_file = cache_dir / f"{cache_key}.json"

    if cache_file.exists():
        journey_data = json.loads(cache_file.read_text())
    else:
        # Build Claude prompt (simplified version of the slow_looking_engine)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Anthropic API key not configured")

        client = Anthropic(api_key=api_key)

        suffix = image_path.suffix.lower()
        media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
        media_type = media_map.get(suffix, "image/jpeg")
        image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode()

        system_prompt = (
            "You are an art educator creating a personalized slow-looking journey. "
            f"The user is at Housen Stage {housen_stage}.{housen_substage}. "
            "Return ONLY valid JSON matching the journey schema."
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": "Create a slow-looking journey for this artwork. Return valid JSON with keys: journey_id, artwork, total_steps, estimated_duration_minutes, steps, welcome_text, final_summary, confidence_score, pedagogical_approach."},
                    ],
                }
            ],
        )

        raw = response.content[0].text
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        journey_data = json.loads(raw.strip())
        journey_data["image_filename"] = body.image_filename
        journey_data["created_at"] = datetime.utcnow().isoformat()
        journey_data["housen_stage"] = housen_stage
        journey_data["housen_substage"] = housen_substage
        journey_data["at_museum"] = body.at_museum

        cache_file.write_text(json.dumps(journey_data, indent=2))

    # Ensure a journey_id exists
    if "journey_id" not in journey_data or not journey_data["journey_id"]:
        journey_data["journey_id"] = str(uuid.uuid4())

    # Persist to Supabase
    db_row = {
        "id": journey_data["journey_id"],
        "user_id": user["id"],
        "artwork_title": journey_data.get("artwork", {}).get("title"),
        "artwork_artist": journey_data.get("artwork", {}).get("artist"),
        "image_filename": body.image_filename,
        "total_steps": journey_data.get("total_steps", 0),
        "estimated_duration_minutes": journey_data.get("estimated_duration_minutes", 0),
        "housen_stage": housen_stage,
        "housen_substage": housen_substage,
        "at_museum": body.at_museum,
        "journey_data": json.dumps(journey_data),
        "created_at": journey_data.get("created_at", datetime.utcnow().isoformat()),
    }
    db.table("journeys").upsert(db_row).execute()

    return journey_data


@router.get("", response_model=list[JourneyListItem])
async def list_journeys(
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Return all journeys for the authenticated user, newest first."""
    result = (
        db.table("journeys")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )

    items: list[JourneyListItem] = []
    for row in result.data or []:
        items.append(
            JourneyListItem(
                journey_id=row["id"],
                artwork={
                    "title": row.get("artwork_title"),
                    "artist": row.get("artwork_artist"),
                },
                total_steps=row.get("total_steps", 0),
                estimated_duration_minutes=row.get("estimated_duration_minutes", 0),
                housen_stage=row.get("housen_stage", 1),
                completed_at=row.get("completed_at"),
                image_filename=row.get("image_filename"),
            )
        )
    return items


@router.get("/{journey_id}", response_model=JourneyResponse)
async def get_journey(
    journey_id: str,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Retrieve a single journey with full step data."""
    result = db.table("journeys").select("*").eq("id", journey_id).eq("user_id", user["id"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Journey not found")

    row = result.data[0]
    journey_data = json.loads(row.get("journey_data", "{}"))
    journey_data["journey_id"] = row["id"]
    journey_data["completed_at"] = row.get("completed_at")
    return journey_data


@router.post("/{journey_id}/complete")
async def complete_journey(
    journey_id: str,
    body: JourneyCompleteRequest,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Mark a journey as completed and update user stats."""
    now = datetime.utcnow().isoformat()

    # Mark journey completed
    db.table("journeys").update({
        "completed_at": now,
        "completion_time_seconds": body.completion_time_seconds,
        "steps_viewed": body.steps_viewed,
    }).eq("id", journey_id).eq("user_id", user["id"]).execute()

    # Update user profile stats
    profile_result = db.table("user_profiles").select("*").eq("id", user["id"]).execute()
    if profile_result.data:
        p = profile_result.data[0]
        db.table("user_profiles").update({
            "journeys_completed": p.get("journeys_completed", 0) + 1,
            "total_time_seconds": p.get("total_time_seconds", 0) + body.completion_time_seconds,
            "last_activity": now,
        }).eq("id", user["id"]).execute()

    return {"success": True, "completed_at": now}
