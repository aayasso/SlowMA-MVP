"""
SlowMA Sky Merging Router
Handles constellation sky merging between users.

Status flow:
  pending → accepted → unmerged (optional)
           → declined
           → expired (automatic, based on expires_at)

Endpoints:
  POST /invite              → creator sends merge invite, gets back invite_code
  POST /accept              → invitee accepts using invite_code
  POST /decline             → invitee declines using invite_code
  POST /unmerge/{merge_id}  → either user ends an active merge
  GET  /status              → get all active and pending merges for current user
  GET  /{merge_id}          → get details of a specific merge
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.database import Client, get_supabase, verify_token

router = APIRouter(prefix="/api/sky-merging", tags=["Sky Merging"])

INVITE_EXPIRY_HOURS = 48


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


def generate_invite_code(db: Client) -> str:
    """Generate a unique 8-character invite code for sky merging."""
    import random
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        code = "".join(random.choices(chars, k=8))
        existing = db.table("sky_merges").select("id").eq("invite_code", code).execute()
        if not existing.data:
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique invite code.")


def get_constellation_snapshot(db: Client, user_id: str) -> dict:
    """
    Capture a snapshot of a user's current constellation data.
    This is stored at the time of merge so both users can see
    what each other's sky looked like when they joined.
    """
    try:
        journeys_resp = db.table("journeys").select(
            "id, artwork_id, artwork_title, artwork_artist, housen_stage_at_time, completed_at, created_at"
        ).eq("user_id", user_id).eq("status", "completed").order(
            "completed_at", desc=False
        ).execute()

        profile_resp = db.table("user_profiles").select(
            "housen_stage, housen_substage, journeys_completed"
        ).eq("id", user_id).execute()

        profile = profile_resp.data[0] if profile_resp.data else {}

        return {
            "user_id": user_id,
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "housen_stage": profile.get("housen_stage", 1),
            "housen_substage": profile.get("housen_substage", 1),
            "journeys_completed": profile.get("journeys_completed", 0),
            "journeys": journeys_resp.data or [],
        }
    except Exception as e:
        print(f"Warning: could not capture constellation snapshot: {e}")
        return {"user_id": user_id, "snapshot_at": datetime.now(timezone.utc).isoformat()}


# ============================================================
# Endpoints
# ============================================================

@router.post("/invite")
async def create_invite(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Creator sends a merge invitation.
    Returns an invite_code the invitee uses to accept.

    Body fields:
    - message (optional): personal note to the invitee
    """
    user_data = get_user_from_token(authorization)
    creator_id = user_data["id"]

    # Check creator doesn't already have a pending outgoing invite
    existing_resp = db.table("sky_merges").select("id").eq(
        "creator_id", creator_id
    ).eq("status", "pending").execute()

    if existing_resp.data:
        raise HTTPException(
            status_code=400,
            detail="You already have a pending merge invitation. Cancel it before sending a new one."
        )

    # Check creator doesn't already have an active merge
    active_resp = db.table("sky_merges").select("id").eq(
        "creator_id", creator_id
    ).eq("status", "accepted").execute()

    active_as_invitee_resp = db.table("sky_merges").select("id").eq(
        "invitee_id", creator_id
    ).eq("status", "accepted").execute()

    if active_resp.data or active_as_invitee_resp.data:
        raise HTTPException(
            status_code=400,
            detail="You already have an active sky merge. Unmerge first before creating a new one."
        )

    invite_code = generate_invite_code(db)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)

    # Capture creator's constellation snapshot at invite time
    creator_snapshot = get_constellation_snapshot(db, creator_id)

    record = {
        "creator_id": creator_id,
        "invite_code": invite_code,
        "status": "pending",
        "expires_at": expires_at.isoformat(),
        "message": body.get("message"),
        "creator_constellation_snapshot": creator_snapshot,
    }

    result = db.table("sky_merges").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create merge invitation.")

    merge = result.data[0]

    return {
        "success": True,
        "invite_code": invite_code,
        "expires_at": merge["expires_at"],
        "message": "Share this code with the person you want to merge skies with.",
        "merge_id": merge["id"],
    }


@router.post("/accept")
async def accept_invite(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Invitee accepts a merge invitation using the invite code.

    Body fields:
    - invite_code (required): 8-character code from the creator
    """
    user_data = get_user_from_token(authorization)
    invitee_id = user_data["id"]

    invite_code = body.get("invite_code", "").strip().upper()
    if not invite_code:
        raise HTTPException(status_code=400, detail="invite_code is required.")

    # Find the invite
    merge_resp = db.table("sky_merges").select("*").eq(
        "invite_code", invite_code
    ).eq("status", "pending").execute()

    if not merge_resp.data:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code.")

    merge = merge_resp.data[0]

    # Can't accept your own invite
    if merge["creator_id"] == invitee_id:
        raise HTTPException(status_code=400, detail="You cannot accept your own merge invitation.")

    # Check invite hasn't expired
    expires_at = datetime.fromisoformat(merge["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        db.table("sky_merges").update({"status": "expired"}).eq("id", merge["id"]).execute()
        raise HTTPException(status_code=400, detail="This invite code has expired.")

    # Check invitee doesn't already have an active merge
    active_resp = db.table("sky_merges").select("id").eq(
        "invitee_id", invitee_id
    ).eq("status", "accepted").execute()

    active_as_creator_resp = db.table("sky_merges").select("id").eq(
        "creator_id", invitee_id
    ).eq("status", "accepted").execute()

    if active_resp.data or active_as_creator_resp.data:
        raise HTTPException(
            status_code=400,
            detail="You already have an active sky merge. Unmerge first before accepting a new one."
        )

    # Capture invitee's constellation snapshot
    invitee_snapshot = get_constellation_snapshot(db, invitee_id)

    # Build merged constellation data combining both users' journeys
    creator_snapshot = merge.get("creator_constellation_snapshot") or {}
    merged_data = {
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "creator": {
            "user_id": merge["creator_id"],
            "housen_stage": creator_snapshot.get("housen_stage", 1),
            "journeys_completed": creator_snapshot.get("journeys_completed", 0),
            "journeys": creator_snapshot.get("journeys", []),
        },
        "invitee": {
            "user_id": invitee_id,
            "housen_stage": invitee_snapshot.get("housen_stage", 1),
            "journeys_completed": invitee_snapshot.get("journeys_completed", 0),
            "journeys": invitee_snapshot.get("journeys", []),
        },
    }

    db.table("sky_merges").update({
        "invitee_id": invitee_id,
        "status": "accepted",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "invitee_constellation_snapshot": invitee_snapshot,
        "merged_constellation_data": merged_data,
    }).eq("id", merge["id"]).execute()

    return {
        "success": True,
        "message": "Skies merged successfully!",
        "merge_id": merge["id"],
        "merged_constellation_data": merged_data,
    }


@router.post("/decline")
async def decline_invite(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Invitee declines a merge invitation.

    Body fields:
    - invite_code (required)
    """
    user_data = get_user_from_token(authorization)
    invitee_id = user_data["id"]

    invite_code = body.get("invite_code", "").strip().upper()
    if not invite_code:
        raise HTTPException(status_code=400, detail="invite_code is required.")

    merge_resp = db.table("sky_merges").select("*").eq(
        "invite_code", invite_code
    ).eq("status", "pending").execute()

    if not merge_resp.data:
        raise HTTPException(status_code=404, detail="Invalid or already resolved invite code.")

    merge = merge_resp.data[0]

    if merge["creator_id"] == invitee_id:
        raise HTTPException(status_code=400, detail="You cannot decline your own invitation.")

    db.table("sky_merges").update({
        "status": "declined",
        "invitee_id": invitee_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", merge["id"]).execute()

    return {
        "success": True,
        "message": "Invitation declined.",
    }


@router.post("/unmerge/{merge_id}")
async def unmerge(
    merge_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Either user in an active merge can unmerge at any time.
    Records who initiated the unmerge and when.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    merge_resp = db.table("sky_merges").select("*").eq(
        "id", merge_id
    ).eq("status", "accepted").execute()

    if not merge_resp.data:
        raise HTTPException(status_code=404, detail="Active merge not found.")

    merge = merge_resp.data[0]

    # Only the two users in the merge can unmerge
    if user_id not in (merge["creator_id"], merge["invitee_id"]):
        raise HTTPException(status_code=403, detail="You are not part of this merge.")

    db.table("sky_merges").update({
        "status": "unmerged",
        "unmerged_at": datetime.now(timezone.utc).isoformat(),
        "unmerged_by": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", merge_id).execute()

    return {
        "success": True,
        "message": "Skies unmerged. Your constellation is your own again.",
    }


@router.get("/status")
async def get_merge_status(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Get all active, pending, and recent merges for the current user.
    Returns both merges the user created and merges they were invited to.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    # Merges where user is creator
    as_creator_resp = db.table("sky_merges").select("*").eq(
        "creator_id", user_id
    ).order("created_at", desc=True).limit(10).execute()

    # Merges where user is invitee
    as_invitee_resp = db.table("sky_merges").select("*").eq(
        "invitee_id", user_id
    ).order("created_at", desc=True).limit(10).execute()

    as_creator = as_creator_resp.data or []
    as_invitee = as_invitee_resp.data or []

    # Find active merge if any
    active_merge = None
    for m in as_creator + as_invitee:
        if m["status"] == "accepted":
            active_merge = m
            break

    # Find pending outgoing invite
    pending_outgoing = next(
        (m for m in as_creator if m["status"] == "pending"), None
    )

    return {
        "active_merge": active_merge,
        "pending_outgoing_invite": pending_outgoing,
        "as_creator": as_creator,
        "as_invitee": as_invitee,
    }


@router.get("/{merge_id}")
async def get_merge(
    merge_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Get full details of a specific merge including constellation data.
    Only accessible by the two users in the merge.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    merge_resp = db.table("sky_merges").select("*").eq("id", merge_id).execute()

    if not merge_resp.data:
        raise HTTPException(status_code=404, detail="Merge not found.")

    merge = merge_resp.data[0]

    if user_id not in (merge["creator_id"], merge.get("invitee_id")):
        raise HTTPException(status_code=403, detail="You are not part of this merge.")

    return merge