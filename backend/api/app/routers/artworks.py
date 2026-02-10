"""
SlowMA Artworks Router
Handles all artwork-related endpoints for the SlowMA API.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import random
from app.database import get_supabase, Client
from app.models.schemas import ArtworkInfo

router = APIRouter(prefix="/api/artworks", tags=["Artworks"])


# ============================================================
# Helper Functions
# ============================================================

def build_artwork_response(artwork_row: dict) -> dict:
    """
    Transform a database row into a clean API response.
    Includes the public URL for the artwork image.
    """
    db = get_supabase()
    
    # Get public URL for the image
    image_url = None
    if artwork_row.get("image_filename"):
        try:
            # Supabase storage public URL format
            image_url = db.storage.from_("artworks").get_public_url(
                artwork_row["image_filename"]
            )
        except Exception as e:
            print(f"Warning: Could not generate image URL: {e}")
    
    return {
        "id": artwork_row["id"],
        "title": artwork_row.get("title"),
        "artist": artwork_row.get("artist"),
        "year": artwork_row.get("year"),
        "period": artwork_row.get("period"),
        "style": artwork_row.get("style"),
        "image_filename": artwork_row.get("image_filename"),
        "image_url": image_url,
        "is_seed_artwork": artwork_row.get("is_seed_artwork", False),
        "created_at": artwork_row.get("created_at"),
    }


# ============================================================
# Endpoints
# ============================================================

@router.get("/")
async def get_all_artworks(
    is_seed_artwork: Optional[bool] = None,
    limit: int = 100,
    db: Client = Depends(get_supabase)
):
    """
    Get all artworks from the database.
    
    Query Parameters:
    - is_seed_artwork: Filter by seed artworks (True) or user-uploaded (False)
    - limit: Maximum number of artworks to return (default 100)
    
    Returns:
    - List of artwork objects with image URLs
    """
    try:
        query = db.table("artworks").select("*")
        
        # Apply filters
        if is_seed_artwork is not None:
            query = query.eq("is_seed_artwork", is_seed_artwork)
        
        # Execute query
        response = query.limit(limit).execute()
        
        if not response.data:
            return {
                "success": True,
                "count": 0,
                "artworks": []
            }
        
        # Transform all rows to include image URLs
        artworks = [build_artwork_response(row) for row in response.data]
        
        return {
            "success": True,
            "count": len(artworks),
            "artworks": artworks
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch artworks: {str(e)}"
        )


@router.get("/seeds")
async def get_seed_artworks(db: Client = Depends(get_supabase)):
    """
    Get only the seed artworks (the 4 starter artworks).
    
    These are the artworks that:
    1. Every user sees when they first open the app
    2. Disappear after completion to reveal the constellation
    
    Returns:
    - List of 4 seed artwork objects
    """
    try:
        response = db.table("artworks").select("*").eq("is_seed_artwork", True).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="No seed artworks found. Database may not be initialized."
            )
        
        artworks = [build_artwork_response(row) for row in response.data]
        
        return {
            "success": True,
            "count": len(artworks),
            "artworks": artworks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch seed artworks: {str(e)}"
        )


@router.get("/random")
async def get_random_artwork(
    is_seed_artwork: bool = True,
    db: Client = Depends(get_supabase)
):
    """
    Get a random artwork from the database.
    
    Query Parameters:
    - is_seed_artwork: Get random seed artwork (True) or random user artwork (False)
    
    Use Case:
    - When user taps "Start Journey" on home screen
    - Returns one random seed artwork for them to observe
    
    Returns:
    - Single artwork object
    """
    try:
        response = db.table("artworks").select("*").eq("is_seed_artwork", is_seed_artwork).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="No artworks available"
            )
        
        # Pick a random artwork from the results
        random_artwork = random.choice(response.data)
        artwork = build_artwork_response(random_artwork)
        
        return {
            "success": True,
            "artwork": artwork
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch random artwork: {str(e)}"
        )


@router.get("/{artwork_id}")
async def get_artwork_by_id(
    artwork_id: str,
    db: Client = Depends(get_supabase)
):
    """
    Get a specific artwork by its ID.
    
    Path Parameters:
    - artwork_id: UUID of the artwork
    
    Returns:
    - Single artwork object with full details
    """
    try:
        response = db.table("artworks").select("*").eq("id", artwork_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"Artwork with id '{artwork_id}' not found"
            )
        
        artwork = build_artwork_response(response.data[0])
        
        return {
            "success": True,
            "artwork": artwork
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch artwork: {str(e)}"
        )


@router.get("/{artwork_id}/info")
async def get_artwork_info(
    artwork_id: str,
    db: Client = Depends(get_supabase)
):
    """
    Get just the basic info about an artwork (no image URL).
    
    This is useful for lightweight requests where you only need
    title/artist/year without loading the full image.
    
    Returns:
    - ArtworkInfo schema (title, artist, year, period, style)
    """
    try:
        response = db.table("artworks").select(
            "title, artist, year, period, style"
        ).eq("id", artwork_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail=f"Artwork with id '{artwork_id}' not found"
            )
        
        return {
            "success": True,
            "artwork_info": response.data[0]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch artwork info: {str(e)}"
        )


@router.get("/user/{user_id}")
async def get_user_artworks(
    user_id: str,
    limit: int = 50,
    db: Client = Depends(get_supabase)
):
    """
    Get all artworks uploaded by a specific user.
    
    Path Parameters:
    - user_id: UUID of the user
    
    Query Parameters:
    - limit: Maximum number of artworks to return (default 50)
    
    Returns:
    - List of artwork objects uploaded by this user
    """
    try:
        response = db.table("artworks").select("*").eq(
            "uploaded_by", user_id
        ).eq("is_seed_artwork", False).limit(limit).execute()
        
        artworks = [build_artwork_response(row) for row in response.data] if response.data else []
        
        return {
            "success": True,
            "count": len(artworks),
            "artworks": artworks
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch user artworks: {str(e)}"
        )