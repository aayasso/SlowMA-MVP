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
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.profile_file = self.data_dir / "user_profile.json"
        self.gallery_dir = self.data_dir / "gallery"
        self.gallery_dir.mkdir(exist_ok=True)
        
        self.active_journey_file = self.data_dir / "active_journey.json"
    
    def load_user_profile(self) -> dict:
        """Load or create user profile"""
        if self.profile_file.exists():
            return json.loads(self.profile_file.read_text())
        
        # Create new profile
        return self._create_new_profile()
    
    def _create_new_profile(self) -> dict:
        """Create a new user profile with default values"""
        profile = {
            "user_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "tutorial_completed": False,
            
            # Housen stage tracking
            "housen_stage": 1,
            "housen_substage": 1,
            "stage_history": [],
            
            # Engagement metrics
            "journeys_completed": 0,
            "total_time_seconds": 0,
            "museum_visits": 0,
            "last_activity": None,
            "recent_quality_scores": [],
            
            # Gamification
            "badges": [],
            "achievements": [],
            
            # Settings
            "notifications_enabled": True,
            "location_permission": False
        }
        
        self.save_user_profile(profile)
        return profile
    
    def save_user_profile(self, profile: dict):
        """Save user profile to disk"""
        self.profile_file.write_text(json.dumps(profile, indent=2))
    
    def save_active_journey(self, journey: dict):
        """Save journey currently in progress"""
        self.active_journey_file.write_text(json.dumps(journey, indent=2))
    
    def load_active_journey(self, journey_id: str) -> dict:
        """Load active journey"""
        if not self.active_journey_file.exists():
            return None
        
        journey = json.loads(self.active_journey_file.read_text())
        if journey.get('journey_id') == journey_id:
            return journey
        
        return None
    
    def save_to_gallery(self, journey: dict, user_profile: dict):
        """Save completed journey to gallery"""
        journey_id = journey['journey_id']
        gallery_file = self.gallery_dir / f"{journey_id}.json"
        
        # Add completion metadata
        journey['user_id'] = user_profile['user_id']
        journey['saved_at'] = datetime.now().isoformat()
        
        gallery_file.write_text(json.dumps(journey, indent=2))
    
    def load_gallery(self, user_profile: dict) -> list:
        """Load all gallery journeys for user"""
        user_id = user_profile['user_id']
        journeys = []
        
        for file in sorted(self.gallery_dir.glob("*.json"), reverse=True):
            try:
                journey = json.loads(file.read_text())
                if journey.get('user_id') == user_id:
                    journeys.append(journey)
            except:
                continue
        
        return journeys
    
    def load_gallery_journey(self, journey_id: str, user_profile: dict) -> dict:
        """Load specific journey from gallery"""
        file = self.gallery_dir / f"{journey_id}.json"
        if not file.exists():
            return None
        
        journey = json.loads(file.read_text())
        if journey.get('user_id') == user_profile['user_id']:
            return journey
        
        return None
    
    def check_and_award_badge(self, user_profile: dict, badge_type: str):
        """Check if user earned a badge and award it"""
        badges_awarded = []
        
        if badge_type == 'time_spent':
            time_minutes = user_profile['total_time_seconds'] / 60
            
            milestones = [
                (30, "time_30min", "First 30 Minutes", "⏱️"),
                (60, "time_1hour", "One Hour of Slow Looking", "🕐"),
                (180, "time_3hours", "Three Hours Invested", "⏰"),
                (300, "time_5hours", "Five Hours Dedicated", "🌟"),
                (600, "time_10hours", "Ten Hours Master", "👑")
            ]
            
            for minutes, badge_id, badge_name, icon in milestones:
                if time_minutes >= minutes and badge_id not in user_profile['badges']:
                    user_profile['badges'].append(badge_id)
                    badges_awarded.append({
                        "id": badge_id,
                        "name": badge_name,
                        "icon": icon,
                        "earned_at": datetime.now().isoformat()
                    })
        
        elif badge_type == 'museum_visitor':
            visits = user_profile['museum_visits']
            
            milestones = [
                (1, "museum_first", "First Museum Visit", "🏛️"),
                (5, "museum_5", "Museum Explorer", "🎨"),
                (10, "museum_10", "Gallery Regular", "🖼️"),
                (25, "museum_25", "Art Pilgrim", "🌍")
            ]
            
            for count, badge_id, badge_name, icon in milestones:
                if visits >= count and badge_id not in user_profile['badges']:
                    user_profile['badges'].append(badge_id)
                    badges_awarded.append({
                        "id": badge_id,
                        "name": badge_name,
                        "icon": icon,
                        "earned_at": datetime.now().isoformat()
                    })
        
        elif badge_type == 'quality_engagement':
            scores = user_profile.get('recent_quality_scores', [])
            if len(scores) >= 5:
                avg_score = sum(scores[-5:]) / 5
                
                milestones = [
                    (70, "quality_good", "Quality Observer", "👁️"),
                    (80, "quality_great", "Keen Eye", "🔍"),
                    (90, "quality_excellent", "Master Observer", "💎")
                ]
                
                for threshold, badge_id, badge_name, icon in milestones:
                    if avg_score >= threshold and badge_id not in user_profile['badges']:
                        user_profile['badges'].append(badge_id)
                        badges_awarded.append({
                            "id": badge_id,
                            "name": badge_name,
                            "icon": icon,
                            "earned_at": datetime.now().isoformat()
                        })
        
        elif badge_type == 'stage_progression':
            stage = user_profile['housen_stage']
            substage = user_profile['housen_substage']
            
            milestones = [
                (2, 1, "stage_2", "Constructive Thinker", "🌱"),
                (3, 1, "stage_3", "Analytical Mind", "🧠"),
                (4, 1, "stage_4", "Interpretive Vision", "🎭"),
                (5, 1, "stage_5", "Re-creative Master", "✨")
            ]
            
            for req_stage, req_substage, badge_id, badge_name, icon in milestones:
                if (stage > req_stage or (stage == req_stage and substage >= req_substage)) and badge_id not in user_profile['badges']:
                    user_profile['badges'].append(badge_id)
                    badges_awarded.append({
                        "id": badge_id,
                        "name": badge_name,
                        "icon": icon,
                        "earned_at": datetime.now().isoformat()
                    })
        
        # Save profile if badges were awarded
        if badges_awarded:
            user_profile['achievements'].extend(badges_awarded)
            self.save_user_profile(user_profile)
        
        return badges_awarded
    
    def get_badge_info(self, badge_id: str) -> dict:
        """Get information about a specific badge"""
        all_badges = {
            # Time badges
            "time_30min": {"name": "First 30 Minutes", "icon": "⏱️", "description": "Spent 30 minutes slow looking"},
            "time_1hour": {"name": "One Hour of Slow Looking", "icon": "🕐", "description": "Dedicated one full hour"},
            "time_3hours": {"name": "Three Hours Invested", "icon": "⏰", "description": "Three hours of mindful observation"},
            "time_5hours": {"name": "Five Hours Dedicated", "icon": "🌟", "description": "Five hours exploring art"},
            "time_10hours": {"name": "Ten Hours Master", "icon": "👑", "description": "Ten hours of deep looking"},
            
            # Museum badges
            "museum_first": {"name": "First Museum Visit", "icon": "🏛️", "description": "Used SlowMA at a museum"},
            "museum_5": {"name": "Museum Explorer", "icon": "🎨", "description": "Five museum visits"},
            "museum_10": {"name": "Gallery Regular", "icon": "🖼️", "description": "Ten museum visits"},
            "museum_25": {"name": "Art Pilgrim", "icon": "🌍", "description": "Twenty-five museum visits"},
            
            # Quality badges
            "quality_good": {"name": "Quality Observer", "icon": "👁️", "description": "Consistent quality engagement"},
            "quality_great": {"name": "Keen Eye", "icon": "🔍", "description": "High quality observations"},
            "quality_excellent": {"name": "Master Observer", "icon": "💎", "description": "Exceptional engagement quality"},
            
            # Stage badges
            "stage_2": {"name": "Constructive Thinker", "icon": "🌱", "description": "Reached Housen Stage 2"},
            "stage_3": {"name": "Analytical Mind", "icon": "🧠", "description": "Reached Housen Stage 3"},
            "stage_4": {"name": "Interpretive Vision", "icon": "🎭", "description": "Reached Housen Stage 4"},
            "stage_5": {"name": "Re-creative Master", "icon": "✨", "description": "Reached Housen Stage 5"}
        }
        
        return all_badges.get(badge_id, {"name": "Unknown", "icon": "❓", "description": ""})
    
    def get_constellation_data(self, user_profile: dict, seed_artworks: list) -> dict:
        """
        Get data for constellation visualization
        
        Returns:
            Dictionary with:
            - current_stage, current_substage
            - journey_count
            - seed_artworks (only if < 10 journeys)
            - journeys (list of completed journeys with positions)
        """
        
        journeys = self.load_gallery(user_profile)
        journey_count = len(journeys)
        
        # Format journey data for constellation
        journey_data = []
        for journey in journeys:
            journey_data.append({
                "journey_id": journey['journey_id'],
                "artwork_title": journey['artwork'].get('title', 'Untitled'),
                "artwork_artist": journey['artwork'].get('artist', 'Unknown'),
                "stage": journey.get('housen_stage', user_profile['housen_stage']),
                "substage": journey.get('housen_substage', user_profile['housen_substage']),
                "completed_at": journey.get('completed_at', ''),
                "image_filename": journey.get('image_filename', '')
            })
        
        return {
            "current_stage": user_profile['housen_stage'],
            "current_substage": user_profile['housen_substage'],
            "journey_count": journey_count,
            "seed_artworks": seed_artworks if journey_count < 10 else [],
            "journeys": journey_data
        }