"""
SlowMA Artworks Router
Image upload, seed artworks, and artwork metadata.
"""

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from supabase import Client

from app.database import get_supabase, verify_token
from app.models.schemas import ArtworkInfo, ArtworkUploadResponse

router = APIRouter(prefix="/artworks", tags=["artworks"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _get_current_user(authorization: str = Header(...)) -> dict:
    token = authorization.replace("Bearer ", "")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


# ---------------------------------------------------------------------------
# Seed artworks — available to all new users
# ---------------------------------------------------------------------------

SEED_ARTWORKS: list[dict] = [
    {
        "title": "Woman with Red Hair",
        "artist": "Amadeo Modigliani",
        "year": "1917",
        "period": "Early 20th Century",
        "style": "Expressionism",
        "image_filename": "seed_modigliani.jpg",
    },
    {
        "title": "Skeleton with a Burning Cigarette",
        "artist": "Vincent van Gogh",
        "year": "1886",
        "period": "Post-Impressionism",
        "style": "Post-Impressionism",
        "image_filename": "seed_vangogh.jpg",
    },
    {
        "title": "The Beheading of Saint John the Baptist",
        "artist": "Caravaggio",
        "year": "1608",
        "period": "Baroque",
        "style": "Baroque",
        "image_filename": "seed_caravaggio.jpg",
    },
    {
        "title": "Meditative Rose",
        "artist": "Salvador Dali",
        "year": "1958",
        "period": "Surrealism",
        "style": "Surrealism",
        "image_filename": "seed_dali.jpg",
    },
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=ArtworkUploadResponse)
async def upload_artwork(
    file: UploadFile = File(...),
    user: dict = Depends(_get_current_user),
):
    """
    Upload an artwork image for analysis.
    Returns the saved filename which can be passed to POST /journeys.
    """
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return ArtworkUploadResponse(
            success=False,
            error=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        return ArtworkUploadResponse(
            success=False,
            error=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    # Save with a unique name
    unique_name = f"{user['id']}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = UPLOAD_DIR / unique_name
    save_path.write_bytes(contents)

    return ArtworkUploadResponse(
        success=True,
        filename=unique_name,
        image_url=f"/uploads/{unique_name}",
    )


@router.get("/seeds", response_model=list[ArtworkInfo])
async def get_seed_artworks():
    """Return the curated seed artworks available for new users."""
    return [
        ArtworkInfo(
            title=s["title"],
            artist=s["artist"],
            year=s["year"],
            period=s["period"],
            style=s["style"],
        )
        for s in SEED_ARTWORKS
    ]


@router.delete("/{filename}")
async def delete_artwork(
    filename: str,
    user: dict = Depends(_get_current_user),
):
    """Delete an uploaded artwork image (only if owned by the user)."""
    # Simple ownership check: filename starts with user id
    if not filename.startswith(user["id"]):
        raise HTTPException(status_code=403, detail="You can only delete your own uploads")

    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return {"success": True, "message": "File deleted"}

    raise HTTPException(status_code=404, detail="File not found")
