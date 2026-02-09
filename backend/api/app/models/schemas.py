"""
SlowMA Pydantic Schemas
All request/response models for the API, derived from the SlowMA domain.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============================================================
# Enums
# ============================================================

class HousenStage(int, Enum):
    ACCOUNTIVE = 1
    CONSTRUCTIVE = 2
    CLASSIFYING = 3
    INTERPRETIVE = 4
    RE_CREATIVE = 5


class HousenSubstage(int, Enum):
    EARLY = 1
    DEVELOPING = 2
    ADVANCED = 3


class ConceptTag(str, Enum):
    COMPOSITION = "composition"
    TECHNIQUE = "technique"
    SYMBOLISM = "symbolism"
    COLOR = "color"
    LIGHT = "light"
    SUBJECT = "subject"
    EMOTION = "emotion"
    CONTEXT = "context"
    STYLE = "style"


class ActivityType(str, Enum):
    TEXT = "text"
    COMPARISON = "comparison"
    CONNECTION = "connection"
    CREATIVE = "creative"
    SYNTHESIS = "synthesis"


class ProgressionChange(str, Enum):
    PROGRESSION = "progression"
    REGRESSION = "regression"
    MAINTENANCE = "maintenance"


# ============================================================
# Auth
# ============================================================

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class AuthResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None
    error: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


# ============================================================
# User Profile
# ============================================================

class UserProfileBase(BaseModel):
    display_name: Optional[str] = None
    housen_stage: int = Field(default=1, ge=1, le=5)
    housen_substage: int = Field(default=1, ge=1, le=3)


class UserProfileCreate(UserProfileBase):
    id: str
    email: str
    is_teacher: bool = False


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None


class UserProfileResponse(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    is_teacher: bool = False
    total_journeys: int = 0
    created_at: str
    updated_at: str


class UserStatsResponse(BaseModel):
    total_journeys: int = 0
    current_stage: int = 1
    current_substage: int = 1
    stage_name: str = "Accountive"
    substage_name: str = "Early"


# ============================================================
# Artwork
# ============================================================

class ArtworkInfo(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    year: Optional[str] = None
    period: Optional[str] = None
    style: Optional[str] = None


class ArtworkUploadResponse(BaseModel):
    success: bool
    filename: Optional[str] = None
    image_url: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# Journey
# ============================================================

class BoundingRegion(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., ge=0.0, le=1.0)
    height: float = Field(..., ge=0.0, le=1.0)
    title: str
    observation: str
    why_notable: str
    soft_prompt: str
    concept_tag: Optional[ConceptTag] = None


class JourneyStep(BaseModel):
    step_number: int
    region: BoundingRegion
    look_away_duration: int = Field(..., ge=15, le=120)
    why_this_sequence: Optional[str] = None
    builds_on: Optional[str] = None


class JourneySummary(BaseModel):
    main_takeaway: str
    connections: str
    invitation_to_return: str
    reflection_question: str


class JourneyCreate(BaseModel):
    """Request body when a user triggers a new journey from an uploaded image."""
    image_filename: str
    at_museum: bool = False


class JourneyResponse(BaseModel):
    journey_id: str
    artwork: ArtworkInfo
    total_steps: int = Field(..., ge=3, le=6)
    estimated_duration_minutes: int
    steps: list[JourneyStep]
    welcome_text: str
    final_summary: JourneySummary
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    pedagogical_approach: Optional[str] = None
    image_filename: Optional[str] = None
    housen_stage: int = 1
    housen_substage: int = 1
    at_museum: bool = False
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class JourneyListItem(BaseModel):
    journey_id: str
    artwork: ArtworkInfo
    total_steps: int
    estimated_duration_minutes: int
    housen_stage: int
    completed_at: Optional[str] = None
    image_filename: Optional[str] = None


class JourneyCompleteRequest(BaseModel):
    """Sent when the user finishes walking through a journey."""
    completion_time_seconds: int = 0
    steps_viewed: int = 0


# ============================================================
# Reflection Activities
# ============================================================

class ReflectionActivity(BaseModel):
    id: str
    type: ActivityType
    title: str
    prompt: str
    placeholder: Optional[str] = None
    why_this_activity: Optional[str] = None


class ReflectionActivitiesResponse(BaseModel):
    journey_id: str
    activities: list[ReflectionActivity]


class ReflectionSubmission(BaseModel):
    """
    Maps activity_id -> user response text.
    e.g. {"activity_1": "I noticed the warm colors...", "activity_2": "..."}
    """
    journey_id: str
    responses: dict[str, str]


class AssessmentScores(BaseModel):
    """Breakdown of scores per growth indicator."""
    activity_id: str
    scores: dict[str, float]


class ReflectionAssessmentResponse(BaseModel):
    new_stage: int
    new_substage: int
    change: ProgressionChange
    quality_score: float
    scores: list[AssessmentScores]
    feedback: str
    stage_name: str
    substage_name: str


# ============================================================
# Assignments (Teacher Features)
# ============================================================

class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    artwork_url: Optional[str] = None
    image_filename: Optional[str] = None
    due_date: Optional[str] = None
    class_id: Optional[str] = None
    target_stage: Optional[int] = Field(default=None, ge=1, le=5)
    max_students: Optional[int] = None


class AssignmentResponse(BaseModel):
    id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    artwork_url: Optional[str] = None
    image_filename: Optional[str] = None
    due_date: Optional[str] = None
    class_id: Optional[str] = None
    target_stage: Optional[int] = None
    invite_code: Optional[str] = None
    created_at: Optional[str] = None
    student_count: int = 0


class AssignmentSubmission(BaseModel):
    assignment_id: str
    journey_id: str


class StudentProgressResponse(BaseModel):
    student_id: str
    username: Optional[str] = None
    housen_stage: int
    housen_substage: int
    journeys_completed: int
    latest_quality_score: Optional[float] = None
    last_activity: Optional[str] = None


class ClassOverview(BaseModel):
    assignment_id: str
    title: str
    total_students: int
    completed_count: int
    average_quality_score: Optional[float] = None
    stage_distribution: dict[int, int] = Field(default_factory=dict)
    students: list[StudentProgressResponse] = Field(default_factory=list)


# ============================================================
# Social — Sky Merging
# ============================================================

class ConstellationStar(BaseModel):
    """One star in a user's constellation (represents a completed journey)."""
    journey_id: str
    title: Optional[str] = None
    artist: Optional[str] = None
    stage_at_completion: int
    completed_at: Optional[str] = None


class ConstellationData(BaseModel):
    user_id: str
    username: Optional[str] = None
    companion_star: dict  # {stage, substage}
    stars: list[ConstellationStar] = Field(default_factory=list)
    journey_count: int = 0


class SkyMergeRequest(BaseModel):
    """Request to merge constellations with another user."""
    target_user_id: str


class SkyMergeResponse(BaseModel):
    success: bool
    merged_sky: Optional[dict] = None
    my_constellation: Optional[ConstellationData] = None
    their_constellation: Optional[ConstellationData] = None
    shared_artworks: list[str] = Field(default_factory=list)
    message: Optional[str] = None


class SharedGalleryItem(BaseModel):
    journey_id: str
    artwork: ArtworkInfo
    user_id: str
    username: Optional[str] = None
    housen_stage: int
    shared_at: Optional[str] = None
    likes: int = 0


class ShareJourneyRequest(BaseModel):
    journey_id: str
    message: Optional[str] = None


# ============================================================
# Generic
# ============================================================

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    environment: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
