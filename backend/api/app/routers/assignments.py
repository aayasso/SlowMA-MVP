"""
SlowMA Assignments Router
Teacher features: create assignments, track student progress, class overviews.
"""

import json
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentSubmission,
    ClassOverview,
    StudentProgressResponse,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def _generate_invite_code() -> str:
    """Generate a short, human-readable invite code."""
    return secrets.token_urlsafe(6).upper()[:8]


# ---------------------------------------------------------------------------
# Teacher endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    body: AssignmentCreate,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Create a new assignment (teacher only)."""
    assignment_id = str(uuid.uuid4())
    invite_code = _generate_invite_code()
    now = datetime.utcnow().isoformat()

    row = {
        "id": assignment_id,
        "teacher_id": user["id"],
        "title": body.title,
        "description": body.description,
        "artwork_url": body.artwork_url,
        "image_filename": body.image_filename,
        "due_date": body.due_date,
        "class_id": body.class_id,
        "target_stage": body.target_stage,
        "max_students": body.max_students,
        "invite_code": invite_code,
        "created_at": now,
    }
    db.table("assignments").insert(row).execute()

    return AssignmentResponse(**row, student_count=0)


@router.get("", response_model=list[AssignmentResponse])
async def list_assignments(
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """List all assignments created by the authenticated teacher."""
    result = (
        db.table("assignments")
        .select("*")
        .eq("teacher_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )

    assignments = []
    for row in result.data or []:
        # Count enrolled students
        enrollment_result = (
            db.table("assignment_enrollments")
            .select("id", count="exact")
            .eq("assignment_id", row["id"])
            .execute()
        )
        count = enrollment_result.count if enrollment_result.count is not None else 0
        assignments.append(AssignmentResponse(**row, student_count=count))

    return assignments


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Get a single assignment by ID."""
    result = db.table("assignments").select("*").eq("id", assignment_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Assignment not found")

    row = result.data[0]
    enrollment_result = (
        db.table("assignment_enrollments")
        .select("id", count="exact")
        .eq("assignment_id", assignment_id)
        .execute()
    )
    count = enrollment_result.count if enrollment_result.count is not None else 0
    return AssignmentResponse(**row, student_count=count)


@router.get("/{assignment_id}/overview", response_model=ClassOverview)
async def get_class_overview(
    assignment_id: str,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """
    Get a class overview: per-student progress, stage distribution,
    and average quality scores for an assignment.
    """
    # Verify teacher owns this assignment
    assignment_result = db.table("assignments").select("*").eq("id", assignment_id).eq("teacher_id", user["id"]).execute()
    if not assignment_result.data:
        raise HTTPException(status_code=404, detail="Assignment not found or not owned by you")

    assignment = assignment_result.data[0]

    # Get enrollments
    enrollment_result = (
        db.table("assignment_enrollments")
        .select("*")
        .eq("assignment_id", assignment_id)
        .execute()
    )

    students: list[StudentProgressResponse] = []
    stage_dist: dict[int, int] = {}
    quality_scores: list[float] = []
    completed_count = 0

    for enrollment in enrollment_result.data or []:
        student_id = enrollment["student_id"]

        # Get student profile
        profile_result = db.table("user_profiles").select("*").eq("id", student_id).execute()
        if not profile_result.data:
            continue

        p = profile_result.data[0]
        stage = p.get("housen_stage", 1)

        # Check if student completed a journey for this assignment
        submission_result = (
            db.table("assignment_submissions")
            .select("*")
            .eq("assignment_id", assignment_id)
            .eq("student_id", student_id)
            .execute()
        )
        has_completed = bool(submission_result.data)
        if has_completed:
            completed_count += 1

        latest_score = None
        recent = p.get("recent_quality_scores", [])
        if recent:
            latest_score = recent[-1]
            quality_scores.append(latest_score)

        stage_dist[stage] = stage_dist.get(stage, 0) + 1

        students.append(
            StudentProgressResponse(
                student_id=student_id,
                username=p.get("username"),
                housen_stage=stage,
                housen_substage=p.get("housen_substage", 1),
                journeys_completed=p.get("journeys_completed", 0),
                latest_quality_score=latest_score,
                last_activity=p.get("last_activity"),
            )
        )

    avg_quality = (sum(quality_scores) / len(quality_scores)) if quality_scores else None

    return ClassOverview(
        assignment_id=assignment_id,
        title=assignment["title"],
        total_students=len(students),
        completed_count=completed_count,
        average_quality_score=round(avg_quality, 1) if avg_quality else None,
        stage_distribution=stage_dist,
        students=students,
    )


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------

@router.post("/join")
async def join_assignment(
    invite_code: str = Query(..., description="The invite code shared by the teacher"),
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Join an assignment using an invite code (student)."""
    result = db.table("assignments").select("*").eq("invite_code", invite_code).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    assignment = result.data[0]

    # Check max students
    if assignment.get("max_students"):
        existing = (
            db.table("assignment_enrollments")
            .select("id", count="exact")
            .eq("assignment_id", assignment["id"])
            .execute()
        )
        if existing.count and existing.count >= assignment["max_students"]:
            raise HTTPException(status_code=400, detail="This assignment is full")

    # Check duplicate enrollment
    existing_enrollment = (
        db.table("assignment_enrollments")
        .select("id")
        .eq("assignment_id", assignment["id"])
        .eq("student_id", user["id"])
        .execute()
    )
    if existing_enrollment.data:
        return {"success": True, "message": "Already enrolled", "assignment_id": assignment["id"]}

    db.table("assignment_enrollments").insert({
        "id": str(uuid.uuid4()),
        "assignment_id": assignment["id"],
        "student_id": user["id"],
        "enrolled_at": datetime.utcnow().isoformat(),
    }).execute()

    return {"success": True, "message": "Enrolled successfully", "assignment_id": assignment["id"]}


@router.post("/submit")
async def submit_assignment(
    body: AssignmentSubmission,
    user: dict = Depends(_get_current_user),
    db: Client = Depends(get_supabase),
):
    """Submit a completed journey as an assignment submission (student)."""
    # Verify enrollment
    enrollment_result = (
        db.table("assignment_enrollments")
        .select("id")
        .eq("assignment_id", body.assignment_id)
        .eq("student_id", user["id"])
        .execute()
    )
    if not enrollment_result.data:
        raise HTTPException(status_code=403, detail="You are not enrolled in this assignment")

    db.table("assignment_submissions").upsert({
        "id": f"{user['id']}_{body.assignment_id}",
        "assignment_id": body.assignment_id,
        "student_id": user["id"],
        "journey_id": body.journey_id,
        "submitted_at": datetime.utcnow().isoformat(),
    }).execute()

    return {"success": True, "message": "Assignment submitted"}
