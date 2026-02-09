"""
SlowMA Social Router
Sky merging (constellation sharing), shared gallery, and social features.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import (
    ConstellationData,
    ConstellationStar,
    SharedGalleryItem,
    ShareJourneyRequest,
    SkyMergeRequest,
    SkyMergeResponse,
)

router = APIRouter(prefix="/social", tags=["social"])


def _get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def _build_constellation(user_id: str, db: Client) -> ConstellationData:
    """Build a user's constellation from their profile and journey history."""
    profile_result = db.table("user_profiles").select("*").eq("id", user_id).execute()
    if not profile_result.data:
        raise HTTPException(status_code=404, detail="User not found")

    p = profile_result.data[0]

    # Fetch completed journeys
    journey_result = (
        db.table("journeys")
        .select("*")
        .eq("user_id", user_id)
        .not_.is_("completed_at", "null")
        .order("completed_at", desc=True)
        .execute()
    )

    stars: list[ConstellationStar] = []
    for row in journey_result.data or []:
        stars.append(
            ConstellationStar(
                journey_id=row["id"],
                title=row.get("artwork_title"),
                artist=row.get("artwork_artist"),
                stage_at_completion=row.get("housen_stage", 1),
                completed_at=row.get("completed_at"),
            )
        )

    return ConstellationData(
        user_id=user_id,
        username=p.get("username"),
        companion_star={
            "stage": p.get("housen_stage", 1),
            "substage": p.get("housen_substage", 1),
        },
        stars=stars,
        journey_count=len(stars),
    )


# ---------------------------------------------------------------------------
# Constellation & Sky Merging
# ---------------------------------------------------------------------------

@router.get("/constellation", response_model=ConstellationData)
async def get_my_constellation(
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Return the authenticated user's constellation data."""
    return _build_constellation(user["id"], db)


@router.post("/sky-merge", response_model=SkyMergeResponse)
async def merge_skies(
    body: SkyMergeRequest,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Merge your constellation with another user's.
    Returns both constellations plus any shared artworks (artworks both
    users have journeyed through).
    """
    if body.target_user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot merge sky with yourself")

    try:
        my_constellation = _build_constellation(user["id"], db)
        their_constellation = _build_constellation(body.target_user_id, db)
    except HTTPException:
        return SkyMergeResponse(success=False, message="Target user not found")

    # Find shared artworks (by title, since artwork_id isn't guaranteed)
    my_titles = {s.title for s in my_constellation.stars if s.title}
    their_titles = {s.title for s in their_constellation.stars if s.title}
    shared = sorted(my_titles & their_titles)

    # Build merged view
    all_stars = []
    for star in my_constellation.stars:
        all_stars.append({
            "journey_id": star.journey_id,
            "title": star.title,
            "artist": star.artist,
            "owner": "me",
            "stage_at_completion": star.stage_at_completion,
        })
    for star in their_constellation.stars:
        all_stars.append({
            "journey_id": star.journey_id,
            "title": star.title,
            "artist": star.artist,
            "owner": "them",
            "stage_at_completion": star.stage_at_completion,
        })

    return SkyMergeResponse(
        success=True,
        merged_sky={
            "total_stars": len(all_stars),
            "stars": all_stars,
            "shared_count": len(shared),
        },
        my_constellation=my_constellation,
        their_constellation=their_constellation,
        shared_artworks=shared,
        message=f"Skies merged! You share {len(shared)} artwork(s) in common.",
    )


# ---------------------------------------------------------------------------
# Shared Gallery
# ---------------------------------------------------------------------------

@router.post("/share")
async def share_journey(
    body: ShareJourneyRequest,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Share a completed journey to the community gallery."""
    # Verify journey exists and belongs to user
    journey_result = (
        db.table("journeys")
        .select("*")
        .eq("id", body.journey_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not journey_result.data:
        raise HTTPException(status_code=404, detail="Journey not found")

    row = journey_result.data[0]

    share_row = {
        "id": str(uuid.uuid4()),
        "journey_id": body.journey_id,
        "user_id": user["id"],
        "artwork_title": row.get("artwork_title"),
        "artwork_artist": row.get("artwork_artist"),
        "image_filename": row.get("image_filename"),
        "housen_stage": row.get("housen_stage", 1),
        "message": body.message,
        "shared_at": datetime.utcnow().isoformat(),
        "likes": 0,
    }
    db.table("shared_gallery").upsert(share_row).execute()

    return {"success": True, "message": "Journey shared to the gallery!"}


@router.get("/gallery", response_model=list[SharedGalleryItem])
async def get_shared_gallery(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Client = Depends(get_supabase),
):
    """Browse the community shared gallery, newest first."""
    result = (
        db.table("shared_gallery")
        .select("*")
        .order("shared_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items: list[SharedGalleryItem] = []
    for row in result.data or []:
        # Resolve username
        username = None
        profile_result = db.table("user_profiles").select("username").eq("id", row.get("user_id", "")).execute()
        if profile_result.data:
            username = profile_result.data[0].get("username")

        items.append(
            SharedGalleryItem(
                journey_id=row.get("journey_id", ""),
                artwork={
                    "title": row.get("artwork_title"),
                    "artist": row.get("artwork_artist"),
                },
                user_id=row.get("user_id", ""),
                username=username,
                housen_stage=row.get("housen_stage", 1),
                shared_at=row.get("shared_at"),
                likes=row.get("likes", 0),
            )
        )
    return items


@router.post("/gallery/{share_id}/like")
async def like_shared_journey(
    share_id: str,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Like a shared gallery item."""
    result = db.table("shared_gallery").select("*").eq("id", share_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Shared item not found")

    current_likes = result.data[0].get("likes", 0)
    db.table("shared_gallery").update({"likes": current_likes + 1}).eq("id", share_id).execute()

    return {"success": True, "likes": current_likes + 1}
