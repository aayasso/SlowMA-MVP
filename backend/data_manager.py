"""
Data Manager
Handles all data persistence for user profiles, journeys, and gallery
"""

import json
from pathlib import Path
from datetime import datetime
import uuid


class DataManager:
    """Manages all data storage and retrieval"""
    
    def __init__(self):
        """Initialize data manager and create necessary directories"""
        self.data_dir = Path('data')
        self.gallery_dir = self.data_dir / 'gallery'
        
        # Create directories if they don't exist
        self.data_dir.mkdir(exist_ok=True)
        self.gallery_dir.mkdir(exist_ok=True)
    
    # ==================== USER PROFILE ====================
    
    def load_user_profile(self) -> dict:
        """Load user profile from local storage"""
        profile_file = self.data_dir / 'user_profile.json'
        
        if profile_file.exists():
            with open(profile_file, 'r') as f:
                profile = json.load(f)
                # Ensure profile has an id field for local storage
                if 'id' not in profile:
                    profile['id'] = 'local-user'
                return profile
        
        # Create default profile with id
        default_profile = {
            'id': 'local-user',
            'housen_stage': 1,
            'housen_substage': 1,
            'journeys_completed': 0,
            'total_time_seconds': 0,
            'last_activity': None,
            'created_at': datetime.now().isoformat(),
            'museum_visits': 0,
            'notifications_enabled': True,
            'location_permission': False
        }
        
        self.save_user_profile(default_profile)
        return default_profile
    
    def save_user_profile(self, profile: dict):
        """Save user profile to local storage"""
        profile_file = self.data_dir / 'user_profile.json'
        profile['updated_at'] = datetime.now().isoformat()
        
        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)
    
    # ==================== JOURNEYS ====================
    
    def save_journey(self, user_id: str, journey: dict):
        """Save a completed journey"""
        journey_id = journey.get('id', str(uuid.uuid4()))
        journey['id'] = journey_id
        journey['user_id'] = user_id
        journey['saved_at'] = datetime.now().isoformat()
        
        # Save to user's gallery
        user_gallery = self.gallery_dir / user_id
        user_gallery.mkdir(exist_ok=True)
        
        journey_file = user_gallery / f"{journey_id}.json"
        with open(journey_file, 'w') as f:
            json.dump(journey, f, indent=2)
    
    def load_journey(self, user_id: str, journey_id: str) -> dict:
        """Load a specific journey"""
        journey_file = self.gallery_dir / user_id / f"{journey_id}.json"
        
        if journey_file.exists():
            with open(journey_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def get_all_journeys(self, user_id: str) -> list:
        """Get all journeys for a user"""
        user_gallery = self.gallery_dir / user_id
        
        if not user_gallery.exists():
            return []
        
        journeys = []
        for journey_file in user_gallery.glob('*.json'):
            with open(journey_file, 'r') as f:
                journey = json.load(f)
                journeys.append(journey)
        
        # Sort by date, newest first
        journeys.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
        return journeys
    
    # ==================== REFLECTIONS ====================
    
    def save_reflection(self, user_id: str, journey_id: str, reflection: dict):
        """Save reflection responses for a journey"""
        reflection_file = self.gallery_dir / user_id / f"{journey_id}_reflection.json"
        
        with open(reflection_file, 'w') as f:
            json.dump(reflection, f, indent=2)
    
    def load_reflection(self, user_id: str, journey_id: str) -> dict:
        """Load reflection for a journey"""
        reflection_file = self.gallery_dir / user_id / f"{journey_id}_reflection.json"
        
        if reflection_file.exists():
            with open(reflection_file, 'r') as f:
                return json.load(f)
        
        return None
    
    # ==================== BADGES ====================
    
    def get_user_badges(self, user_id: str) -> list:
        """Get all badges earned by user"""
        badges_file = self.data_dir / f"{user_id}_badges.json"
        
        if badges_file.exists():
            with open(badges_file, 'r') as f:
                return json.load(f)
        
        return []
    
    def add_badge(self, user_id: str, badge_id: str):
        """Add a badge to user's collection"""
        badges = self.get_user_badges(user_id)
        
        # Don't add duplicate badges
        if badge_id not in [b['id'] for b in badges]:
            badge_info = self.get_badge_info(badge_id)
            badge_info['earned_at'] = datetime.now().isoformat()
            badges.append(badge_info)
            
            badges_file = self.data_dir / f"{user_id}_badges.json"
            with open(badges_file, 'w') as f:
                json.dump(badges, f, indent=2)
    
    def get_badge_info(self, badge_id: str) -> dict:
        """Get badge information"""
        # Define all available badges
        all_badges = {
            'first_journey': {
                'id': 'first_journey',
                'name': 'First Steps',
                'icon': '🎨',
                'description': 'Completed your first slow looking journey'
            },
            'early_bird': {
                'id': 'early_bird',
                'name': 'Early Bird',
                'icon': '🌅',
                'description': 'Completed 5 journeys'
            },
            'dedicated': {
                'id': 'dedicated',
                'name': 'Dedicated Viewer',
                'icon': '⭐',
                'description': 'Completed 10 journeys'
            },
            'museum_visitor': {
                'id': 'museum_visitor',
                'name': 'Museum Visitor',
                'icon': '🏛️',
                'description': 'Completed a journey at a museum'
            },
            'time_devotion': {
                'id': 'time_devotion',
                'name': 'Time Devotion',
                'icon': '⏰',
                'description': 'Spent over 1 hour in slow looking'
            },
            'stage_two': {
                'id': 'stage_two',
                'name': 'Growing Insight',
                'icon': '🌱',
                'description': 'Reached Housen Stage II'
            },
            'stage_three': {
                'id': 'stage_three',
                'name': 'Pattern Recognition',
                'icon': '🔍',
                'description': 'Reached Housen Stage III'
            },
            'stage_four': {
                'id': 'stage_four',
                'name': 'Deep Understanding',
                'icon': '💡',
                'description': 'Reached Housen Stage IV'
            },
            'stage_five': {
                'id': 'stage_five',
                'name': 'Master Viewer',
                'icon': '👑',
                'description': 'Reached Housen Stage V'
            }
        }
        
        return all_badges.get(badge_id, {"name": "Unknown", "icon": "❓", "description": ""})
    
    # ==================== STATS ====================
    
    def get_user_stats(self, user_id: str) -> dict:
        """Get user statistics"""
        journeys = self.get_all_journeys(user_id)
        profile = self.load_user_profile()
        
        return {
            'total_journeys': len(journeys),
            'total_time': profile.get('total_time_seconds', 0),
            'museum_visits': profile.get('museum_visits', 0),
            'current_stage': profile.get('housen_stage', 1),
            'current_substage': profile.get('housen_substage', 1),
            'badges_earned': len(self.get_user_badges(user_id))
        }
    
    # ==================== CONSTELLATION DATA ====================
    
    def get_constellation_data(self, user_profile: dict, seed_artworks: list) -> dict:
        """
        Get data for constellation visualization
        
        Args:
            user_profile: User profile data
            seed_artworks: List of seed artwork data
            
        Returns:
            Dict with constellation data
        """
        user_id = user_profile.get('id', 'local-user')
        journeys = self.get_all_journeys(user_id)
        
        # Convert journeys to star data
        journey_stars = []
        for journey in journeys:
            journey_stars.append({
                'id': journey.get('id'),
                'title': journey.get('artwork_title', 'Unknown'),
                'artist': journey.get('artwork_artist', 'Unknown'),
                'completed_at': journey.get('completed_at'),
                'stage': journey.get('housen_stage_at_time', 1),
                'substage': journey.get('housen_substage_at_time', 1),
                'thumbnail': journey.get('image_url', journey.get('image_filename'))
            })
        
        # Only show seed artworks if user has completed fewer than 10 journeys
        show_seeds = len(journeys) < 10
        
        return {
            'companion_star': {
                'stage': user_profile.get('housen_stage', 1),
                'substage': user_profile.get('housen_substage', 1)
            },
            'journeys': journey_stars,
            'journey_count': len(journeys),
            'seed_artworks': seed_artworks if show_seeds else [],
            'show_seeds': show_seeds
        }