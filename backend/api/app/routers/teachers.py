"""
SlowMA Teachers Router
Handles all teacher-facing features:
- Classroom creation and management
- Student enrollment via invite codes
- Assignment creation and tracking
- Student progress dashboard
"""

import random
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from app.database import Client, get_supabase, verify_token

router = APIRouter(prefix="/api/teachers", tags=["Teachers"])


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


def require_teacher(user_id: str, db: Client):
    """Raise 403 if the user is not a teacher."""
    profile = db.table("user_profiles").select(
        "is_teacher"
    ).eq("id", user_id).execute()

    if not profile.data or not profile.data[0].get("is_teacher"):
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available to teacher accounts."
        )


def generate_invite_code(length: int = 6) -> str:
    """Generate a random uppercase invite code, e.g. 'AX7K2P'."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(chars, k=length))


def unique_invite_code(db: Client, table: str) -> str:
    """Generate an invite code that doesn't already exist in the given table."""
    for _ in range(10):
        code = generate_invite_code()
        existing = db.table(table).select("id").eq("invite_code", code).execute()
        if not existing.data:
            return code
    raise HTTPException(status_code=500, detail="Could not generate unique invite code.")


STAGE_NAMES = {
    1: "Accountive",
    2: "Constructive",
    3: "Classifying",
    4: "Interpretive",
    5: "Re-creative",
}


# ============================================================
# Classroom Endpoints
# ============================================================

@router.post("/classrooms")
async def create_classroom(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Create a new classroom.

    Body fields:
    - name (required): e.g. "Period 3 Art"
    - grade_level (optional): e.g. "8"
    - subject (optional): e.g. "Visual Arts"
    - school_id (optional): UUID of the school
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Classroom name is required.")

    invite_code = unique_invite_code(db, "classrooms")

    record = {
        "teacher_id": user_id,
        "name": name,
        "grade_level": body.get("grade_level"),
        "subject": body.get("subject"),
        "school_id": body.get("school_id"),
        "invite_code": invite_code,
        "status": "active",
        "student_count": 0,
    }

    result = db.table("classrooms").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create classroom.")

    return {
        "success": True,
        "classroom": result.data[0],
    }


@router.get("/classrooms")
async def list_classrooms(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """Get all classrooms belonging to the authenticated teacher."""
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    result = db.table("classrooms").select("*").eq(
        "teacher_id", user_id
    ).order("created_at", desc=True).execute()

    return {
        "classrooms": result.data or [],
        "total": len(result.data or []),
    }


@router.get("/classrooms/{classroom_id}")
async def get_classroom(
    classroom_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """Get a single classroom with enrolled student count."""
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    result = db.table("classrooms").select("*").eq(
        "id", classroom_id
    ).eq("teacher_id", user_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Classroom not found.")

    return result.data[0]


@router.delete("/classrooms/{classroom_id}")
async def archive_classroom(
    classroom_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """Archive a classroom (soft delete — sets status to 'archived')."""
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    result = db.table("classrooms").update({
        "status": "archived",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", classroom_id).eq("teacher_id", user_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Classroom not found.")

    return {"success": True, "message": "Classroom archived."}


# ============================================================
# Enrollment Endpoints
# ============================================================

@router.post("/classrooms/join")
async def join_classroom(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Student joins a classroom using an invite code.

    Body fields:
    - invite_code (required): 6-character code from teacher
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]

    invite_code = body.get("invite_code", "").strip().upper()
    if not invite_code:
        raise HTTPException(status_code=400, detail="Invite code is required.")

    # Find classroom
    classroom_resp = db.table("classrooms").select("*").eq(
        "invite_code", invite_code
    ).eq("status", "active").execute()

    if not classroom_resp.data:
        raise HTTPException(status_code=404, detail="Invalid or expired invite code.")

    classroom = classroom_resp.data[0]
    classroom_id = classroom["id"]

    # Check not already enrolled
    existing = db.table("classroom_enrollments").select("id").eq(
        "classroom_id", classroom_id
    ).eq("student_id", user_id).execute()

    if existing.data:
        return {
            "success": True,
            "message": "Already enrolled in this classroom.",
            "classroom": classroom,
        }

    # Get student profile snapshot
    profile_resp = db.table("user_profiles").select(
        "housen_stage, housen_substage, grade_level"
    ).eq("id", user_id).execute()

    profile = profile_resp.data[0] if profile_resp.data else {}

    # Enroll student
    enrollment = {
        "classroom_id": classroom_id,
        "student_id": user_id,
        "status": "active",
        "housen_stage_at_enrollment": profile.get("housen_stage", 1),
        "housen_substage_at_enrollment": profile.get("housen_substage", 1),
        "grade_level_at_enrollment": profile.get("grade_level"),
    }

    db.table("classroom_enrollments").insert(enrollment).execute()

    # Increment student_count on classroom
    db.table("classrooms").update({
        "student_count": classroom.get("student_count", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", classroom_id).execute()

    return {
        "success": True,
        "message": f"Successfully joined {classroom['name']}.",
        "classroom": classroom,
    }


@router.get("/classrooms/{classroom_id}/students")
async def list_students(
    classroom_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Get all students enrolled in a classroom with their current Housen stage.
    Teacher only.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    # Verify teacher owns this classroom
    classroom_resp = db.table("classrooms").select("id, name").eq(
        "id", classroom_id
    ).eq("teacher_id", user_id).execute()

    if not classroom_resp.data:
        raise HTTPException(status_code=404, detail="Classroom not found.")

    # Get enrollments
    enrollments_resp = db.table("classroom_enrollments").select(
        "student_id, enrolled_at, housen_stage_at_enrollment, housen_substage_at_enrollment, grade_level_at_enrollment"
    ).eq("classroom_id", classroom_id).eq("status", "active").execute()

    if not enrollments_resp.data:
        return {"students": [], "total": 0}

    # Get current profiles for each student
    student_ids = [e["student_id"] for e in enrollments_resp.data]
    profiles_resp = db.table("user_profiles").select(
        "id, username, email, housen_stage, housen_substage, journeys_completed, last_activity"
    ).in_("id", student_ids).execute()

    profiles_by_id = {p["id"]: p for p in (profiles_resp.data or [])}

    students = []
    for enrollment in enrollments_resp.data:
        sid = enrollment["student_id"]
        profile = profiles_by_id.get(sid, {})
        current_stage = profile.get("housen_stage", 1)

        students.append({
            "student_id": sid,
            "username": profile.get("username"),
            "email": profile.get("email"),
            "current_stage": current_stage,
            "current_substage": profile.get("housen_substage", 1),
            "stage_name": STAGE_NAMES.get(current_stage, "Unknown"),
            "stage_at_enrollment": enrollment.get("housen_stage_at_enrollment"),
            "journeys_completed": profile.get("journeys_completed", 0),
            "last_activity": profile.get("last_activity"),
            "enrolled_at": enrollment.get("enrolled_at"),
            "grade_level": enrollment.get("grade_level_at_enrollment"),
        })

    return {
        "classroom": classroom_resp.data[0],
        "students": students,
        "total": len(students),
    }


# ============================================================
# Assignment Endpoints
# ============================================================

@router.post("/assignments")
async def create_assignment(
    body: dict,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Create a new assignment for a classroom.

    Body fields:
    - title (required)
    - classroom_id (required)
    - description (optional)
    - artwork_id (optional): UUID of a seed artwork
    - image_filename (optional): for uploaded artwork
    - due_date (optional): ISO timestamp
    - target_stage (optional): 1-5
    - max_students (optional)
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Assignment title is required.")

    classroom_id = body.get("classroom_id")
    if not classroom_id:
        raise HTTPException(status_code=400, detail="classroom_id is required.")

    # Verify teacher owns this classroom
    classroom_resp = db.table("classrooms").select("id").eq(
        "id", classroom_id
    ).eq("teacher_id", user_id).execute()

    if not classroom_resp.data:
        raise HTTPException(status_code=404, detail="Classroom not found.")

    invite_code = unique_invite_code(db, "assignments")

    record = {
        "teacher_id": user_id,
        "classroom_id": classroom_id,
        "title": title,
        "description": body.get("description"),
        "artwork_id": body.get("artwork_id"),
        "image_filename": body.get("image_filename"),
        "due_date": body.get("due_date"),
        "target_stage": body.get("target_stage"),
        "max_students": body.get("max_students"),
        "invite_code": invite_code,
        "status": "active",
    }

    result = db.table("assignments").insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create assignment.")

    return {
        "success": True,
        "assignment": result.data[0],
    }


@router.get("/assignments")
async def list_assignments(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """Get all assignments created by the authenticated teacher."""
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    result = db.table("assignments").select("*").eq(
        "teacher_id", user_id
    ).order("created_at", desc=True).execute()

    return {
        "assignments": result.data or [],
        "total": len(result.data or []),
    }


@router.get("/assignments/{assignment_id}/progress")
async def get_assignment_progress(
    assignment_id: str,
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    Get student progress on a specific assignment.
    Shows who has completed it and their Housen stage before/after.
    Teacher only.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    # Verify teacher owns this assignment
    assignment_resp = db.table("assignments").select("*").eq(
        "id", assignment_id
    ).eq("teacher_id", user_id).execute()

    if not assignment_resp.data:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    assignment = assignment_resp.data[0]

    # Get all student submissions for this assignment
    submissions_resp = db.table("assignment_students").select("*").eq(
        "assignment_id", assignment_id
    ).execute()

    submissions = submissions_resp.data or []
    student_ids = [s["student_id"] for s in submissions]

    # Get student profiles
    profiles = {}
    if student_ids:
        profiles_resp = db.table("user_profiles").select(
            "id, username, email, housen_stage, housen_substage, journeys_completed"
        ).in_("id", student_ids).execute()
        profiles = {p["id"]: p for p in (profiles_resp.data or [])}

    # Build progress list
    completed = [s for s in submissions if s.get("status") == "completed"]
    in_progress = [s for s in submissions if s.get("status") != "completed"]

    student_progress = []
    for sub in submissions:
        sid = sub["student_id"]
        profile = profiles.get(sid, {})
        current_stage = profile.get("housen_stage", 1)

        student_progress.append({
            "student_id": sid,
            "username": profile.get("username"),
            "status": sub.get("status", "assigned"),
            "current_stage": current_stage,
            "current_substage": profile.get("housen_substage", 1),
            "stage_name": STAGE_NAMES.get(current_stage, "Unknown"),
            "stage_at_assignment": sub.get("housen_stage_at_assignment"),
            "stage_at_completion": sub.get("housen_stage_at_completion"),
            "journeys_completed": profile.get("journeys_completed", 0),
            "assigned_at": sub.get("assigned_at"),
            "completed_at": sub.get("completed_at"),
        })

    # Stage distribution across students
    stage_distribution = {}
    for p in profiles.values():
        stage = p.get("housen_stage", 1)
        stage_distribution[stage] = stage_distribution.get(stage, 0) + 1

    return {
        "assignment": assignment,
        "total_students": len(submissions),
        "completed_count": len(completed),
        "in_progress_count": len(in_progress),
        "completion_rate": round(len(completed) / len(submissions), 2) if submissions else 0,
        "stage_distribution": stage_distribution,
        "students": student_progress,
    }


# ============================================================
# Teacher Dashboard
# ============================================================

@router.get("/dashboard")
async def teacher_dashboard(
    authorization: str = Header(...),
    db: Client = Depends(get_supabase),
):
    """
    High-level dashboard for a teacher.
    Shows all classrooms, total students, and stage distribution across all students.
    """
    user_data = get_user_from_token(authorization)
    user_id = user_data["id"]
    require_teacher(user_id, db)

    # Get all classrooms
    classrooms_resp = db.table("classrooms").select("*").eq(
        "teacher_id", user_id
    ).eq("status", "active").execute()

    classrooms = classrooms_resp.data or []
    classroom_ids = [c["id"] for c in classrooms]

    if not classroom_ids:
        return {
            "total_classrooms": 0,
            "total_students": 0,
            "classrooms": [],
            "stage_distribution": {},
        }

    # Get all enrollments across all classrooms
    enrollments_resp = db.table("classroom_enrollments").select(
        "student_id, classroom_id"
    ).in_("classroom_id", classroom_ids).eq("status", "active").execute()

    enrollments = enrollments_resp.data or []
    all_student_ids = list({e["student_id"] for e in enrollments})

    # Get student profiles
    stage_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    if all_student_ids:
        profiles_resp = db.table("user_profiles").select(
            "id, housen_stage"
        ).in_("id", all_student_ids).execute()

        for p in (profiles_resp.data or []):
            stage = p.get("housen_stage", 1)
            stage_distribution[stage] = stage_distribution.get(stage, 0) + 1

    # Add student counts per classroom
    students_per_classroom = {}
    for e in enrollments:
        cid = e["classroom_id"]
        students_per_classroom[cid] = students_per_classroom.get(cid, 0) + 1

    for classroom in classrooms:
        classroom["enrolled_students"] = students_per_classroom.get(classroom["id"], 0)

    return {
        "total_classrooms": len(classrooms),
        "total_students": len(all_student_ids),
        "classrooms": classrooms,
        "stage_distribution": {
            STAGE_NAMES[k]: v for k, v in stage_distribution.items() if v > 0
        },
    }