"""
SlowMA Backend API
Main FastAPI application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import users, journeys, reflections, artworks, assignments, social, teachers, sky_merging

# Initialize FastAPI app
app = FastAPI(
    title="SlowMA API",
    description="Backend API for SlowMA - Mindful Art Observation App",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(journeys.router)
app.include_router(reflections.router)
app.include_router(artworks.router)
app.include_router(assignments.router)
app.include_router(social.router)
app.include_router(teachers.router)
app.include_router(sky_merging.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to SlowMA API",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "slowma-backend"
    }

@app.get("/test-db")
async def test_database():
    """Test Supabase database connection"""
    from app.database import get_supabase

    try:
        db = get_supabase()
        result = db.table('artworks').select('*', count='exact').execute()

        return {
            "status": "success",
            "artworks_count": result.count,
            "message": "Database connection working!"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }