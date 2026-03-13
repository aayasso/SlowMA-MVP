"""
SlowMA Venues Router
Handles museum and gallery location detection, visit tracking,
and donation/purchase prompt logging.

Endpoints:
  GET  /nearby                        → find venues near user's GPS coordinates
  POST /visits/start                  → start a venue visit session
  POST /visits/{visit_id}/end         → end a venue visit session
  POST /visits/{visit_id}/artwork     → log an artwork observation during a visit
  POST /prompts/log                   → log a donation/purchase prompt shown to user
  GET  /{venue_id}                    → get venue details
"""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.database import Client, get_supabase, verify_token

router = APIRouter(prefix="/api/venues", tags=["Venues"])


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


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Calculate distance in meters between two GPS coordinates
    using the Haversine formula.
    """
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return int(R * c)


def get_time_of_day(dt: datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def is_classroom_student(db: Client, user_id: str) -> bool:
    """Check if user is currently enrolled in an active classroom."""
    try:
        result = db.table("classroom_enrollments").select("id").eq(
            "student_id", user_id
        ).eq("status", "active").limit(1).execute()
        return bool(result.data)
    except Exception:
        return False


# ============================================================
# Endpoints
# ============================================================

@router.get("/nearby")
async def get_nearby_venues(
    latitude: float,
    longitude: float,
    radius_m: int = 500,
    venue_type: Optional[str] = None,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Find venues near the user's GPS coordinates.
    Returns venues within radius_m meters, sorted by distance.

    Query params:
    - latitude (required)
    - longitude (required)
    - radius_m (optional, default 500): search radius in meters
    - venue_type (optional): 'museum' or 'gallery'
    """
    get_user_from_token(authorization)

    query = db.table("venues").select("*").eq("verified", True)
    if venue_type:
        query = query.eq("type", venue_type)

    result = query.execute()
    all_venues = result.data or []

    # Filter by distance using Haversine formula
    nearby = []
    for venue in all_venues:
        distance = haversine_distance(
            latitude, longitude,
            float(venue["latitude"]), float(venue["longitude"])
        )
        # Use venue's own detection radius if tighter than the search radius
        threshold = min(radius_m, venue.get("detection_radius_m", 200))
        if distance <= threshold:
            venue["distance_meters"] = distance
            nearby.append(venue)

    # Sort by distance
    nearby.sort(key=lambda v: v["distance_meters"])

    return {
        "venues": nearby,
        "total": len(nearby),
        "search_radius_m": radius_m,
        "user_latitude": latitude,
        "user_longitude": longitude,
    }


@router.get("/{venue_id}")
async def get_venue(
    venue_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """Get full details for a specific venue."""
    get_user_from_token(authorization)

    result = db.table("venues").select("*").eq("id", venue_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Venue not found.")

    return result.data[0]


@router.post("/visits/start")
async def start_visit(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Start a venue visit session when a user arrives at a venue.
    Called when GPS detects a venue or user manually selects one.

    Body fields:
    - venue_id (required)
    - detected_by (required): 'gps' or 'manual'
    - user_latitude (optional): GPS coordinates at detection
    - user_longitude (optional)
    - anonymous_session_id (optional): for anonymous users
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    venue_id = body.get("venue_id")
    if not venue_id:
        raise HTTPException(status_code=400, detail="venue_id is required.")

    detected_by = body.get("detected_by", "manual")
    user_lat = body.get("user_latitude")
    user_lon = body.get("user_longitude")

    # Get venue details
    venue_resp = db.table("venues").select("*").eq("id", venue_id).execute()
    if not venue_resp.data:
        raise HTTPException(status_code=404, detail="Venue not found.")
    venue = venue_resp.data[0]

    # Calculate distance if GPS coords provided
    distance_m = None
    if user_lat and user_lon:
        distance_m = haversine_distance(
            float(user_lat), float(user_lon),
            float(venue["latitude"]), float(venue["longitude"])
        )

    # Get user profile snapshot
    profile_resp = db.table("user_profiles").select(
        "housen_stage, housen_substage, location_prompts_enabled"
    ).eq("id", user_id).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}

    # Check if classroom student
    student = is_classroom_student(db, user_id)

    # Count prior visits to this venue
    prior_visits_resp = db.table("venue_visits").select(
        "id", count="exact"
    ).eq("user_id", user_id).eq("venue_id", venue_id).execute()
    visit_number = (prior_visits_resp.count or 0) + 1

    # Count total prior venue visits
    total_prior_resp = db.table("venue_visits").select(
        "id", count="exact"
    ).eq("user_id", user_id).execute()
    total_prior = total_prior_resp.count or 0

    now = datetime.now(timezone.utc)

    record = {
        "user_id": user_id,
        "is_anonymous": False,
        "venue_id": venue_id,
        "venue_type": venue["type"],
        "detected_by": detected_by,
        "user_latitude": user_lat,
        "user_longitude": user_lon,
        "distance_from_venue_m": distance_m,
        "visit_date": now.date().isoformat(),
        "visit_day_of_week": now.strftime("%A"),
        "visit_time_of_day": get_time_of_day(now),
        "visit_started_at": now.isoformat(),
        "housen_stage_at_arrival": profile.get("housen_stage", 1),
        "housen_substage_at_arrival": profile.get("housen_substage", 1),
        "visit_number_at_venue": visit_number,
        "total_prior_venue_visits": total_prior,
        "is_classroom_student": student,
    }

    result = db.table("venue_visits").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to start venue visit.")

    visit = result.data[0]

    # Determine if prompt should be shown after walkthroughs
    show_prompts = (
        not student
        and profile.get("location_prompts_enabled", True)
    )

    return {
        "success": True,
        "visit_id": visit["id"],
        "venue": venue,
        "visit_number_at_venue": visit_number,
        "show_prompts": show_prompts,
    }


@router.post("/visits/{visit_id}/end")
async def end_visit(
    visit_id: str,
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    End a venue visit session.
    Called when user leaves the venue or closes the app.

    Body fields:
    - total_minutes_in_app (optional): time spent in app during visit
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    visit_resp = db.table("venue_visits").select("*").eq(
        "id", visit_id
    ).eq("user_id", user_id).execute()

    if not visit_resp.data:
        raise HTTPException(status_code=404, detail="Visit not found.")

    visit = visit_resp.data[0]

    # Get current profile for departure stage
    profile_resp = db.table("user_profiles").select(
        "housen_stage, housen_substage"
    ).eq("id", user_id).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}

    # Count artworks observed during this visit
    obs_resp = db.table("venue_artwork_observations").select(
        "id", count="exact"
    ).eq("venue_visit_id", visit_id).execute()
    artworks_observed = obs_resp.count or 0

    now = datetime.now(timezone.utc)

    # Calculate total minutes if not provided
    total_minutes = body.get("total_minutes_in_app")
    if not total_minutes and visit.get("visit_started_at"):
        started = datetime.fromisoformat(
            visit["visit_started_at"].replace("Z", "+00:00")
        )
        total_minutes = int((now - started).total_seconds() / 60)

    db.table("venue_visits").update({
        "visit_ended_at": now.isoformat(),
        "total_minutes_in_app": total_minutes,
        "artworks_observed": artworks_observed,
        "housen_stage_at_departure": profile.get("housen_stage"),
        "housen_substage_at_departure": profile.get("housen_substage"),
        "updated_at": now.isoformat(),
    }).eq("id", visit_id).execute()

    return {
        "success": True,
        "visit_id": visit_id,
        "total_minutes_in_app": total_minutes,
        "artworks_observed": artworks_observed,
    }


@router.post("/visits/{visit_id}/artwork")
async def log_artwork_observation(
    visit_id: str,
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Log a single artwork observation during a venue visit.
    Called after a journey is completed at a venue.

    Body fields:
    - journey_id (optional)
    - walkthrough_seconds (optional)
    - reflection_seconds (optional)
    - emotional_words_selected (optional): list of words from word cloud
    - descriptive_words (optional): words from text/listing activities
    - response_word_count (optional)
    - response_quality_score (optional)
    - activity_types_completed (optional): list of activity type strings
    - housen_stage (optional)
    - housen_substage (optional)
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    visit_resp = db.table("venue_visits").select("*").eq(
        "id", visit_id
    ).eq("user_id", user_id).execute()

    if not visit_resp.data:
        raise HTTPException(status_code=404, detail="Visit not found.")

    visit = visit_resp.data[0]

    # Get observation number for this visit
    obs_count_resp = db.table("venue_artwork_observations").select(
        "id", count="exact"
    ).eq("venue_visit_id", visit_id).execute()
    observation_number = (obs_count_resp.count or 0) + 1

    walkthrough_s = body.get("walkthrough_seconds", 0)
    reflection_s = body.get("reflection_seconds", 0)
    total_s = walkthrough_s + reflection_s

    record = {
        "venue_visit_id": visit_id,
        "venue_id": visit["venue_id"],
        "journey_id": body.get("journey_id"),
        "user_id": user_id,
        "observation_number": observation_number,
        "walkthrough_seconds": walkthrough_s,
        "reflection_seconds": reflection_s,
        "total_seconds": total_s,
        "emotional_words_selected": body.get("emotional_words_selected"),
        "descriptive_words": body.get("descriptive_words"),
        "response_word_count": body.get("response_word_count"),
        "response_quality_score": body.get("response_quality_score"),
        "activity_types_completed": body.get("activity_types_completed"),
        "housen_stage": body.get("housen_stage"),
        "housen_substage": body.get("housen_substage"),
    }

    result = db.table("venue_artwork_observations").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to log artwork observation.")

    # Update artworks_observed count on the visit
    db.table("venue_visits").update({
        "artworks_observed": observation_number,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", visit_id).execute()

    return {
        "success": True,
        "observation_id": result.data[0]["id"],
        "observation_number": observation_number,
    }


@router.post("/prompts/log")
async def log_prompt(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Log a donation or purchase prompt shown to a user.
    Call once when prompt is shown, then again when user responds.

    Body fields:
    - venue_id (required)
    - prompt_type (required): 'donation' or 'purchase'
    - venue_visit_id (optional)
    - journey_id (optional)
    - was_tapped (optional): true if user tapped the CTA
    - was_dismissed (optional): true if user dismissed
    - seconds_visible (optional): how long prompt was on screen
    - detected_by (optional): 'gps' or 'manual'
    - distance_from_venue_m (optional)
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    venue_id = body.get("venue_id")
    prompt_type = body.get("prompt_type")

    if not venue_id:
        raise HTTPException(status_code=400, detail="venue_id is required.")
    if prompt_type not in ("donation", "purchase"):
        raise HTTPException(status_code=400, detail="prompt_type must be 'donation' or 'purchase'.")

    # Get venue for prompt text
    venue_resp = db.table("venues").select(
        "prompt_title, prompt_cta, donation_url, purchase_url"
    ).eq("id", venue_id).execute()

    venue = venue_resp.data[0] if venue_resp.data else {}
    action_url = venue.get("donation_url") if prompt_type == "donation" else venue.get("purchase_url")

    record = {
        "user_id": user_id,
        "is_anonymous": False,
        "venue_id": venue_id,
        "venue_visit_id": body.get("venue_visit_id"),
        "journey_id": body.get("journey_id"),
        "prompt_type": prompt_type,
        "prompt_title": venue.get("prompt_title"),
        "prompt_cta": venue.get("prompt_cta"),
        "action_url": action_url,
        "was_tapped": body.get("was_tapped", False),
        "was_dismissed": body.get("was_dismissed", False),
        "seconds_visible": body.get("seconds_visible"),
        "detected_by": body.get("detected_by"),
        "distance_from_venue_m": body.get("distance_from_venue_m"),
    }

    result = db.table("venue_prompt_logs").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to log prompt.")

    return {
        "success": True,
        "prompt_log_id": result.data[0]["id"],
    }