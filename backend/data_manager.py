"""
Data Manager - Handles all data persistence
Manages user profiles, journeys, and reflections
"""

import json
import os
from pathlib import Path
from datetime import datetime

class DataManager:
    def __init__(self):
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        
        # User data file
        self.user_file = self.data_dir / 'user_profile.json'
        
        # Journeys directory
        self.journeys_dir = self.data_dir / 'journeys'
        self.journeys_dir.mkdir(exist_ok=True)
        
        # Reflections directory
        self.reflections_dir = self.data_dir / 'reflections'
        self.reflections_dir.mkdir(exist_ok=True)
    
    def load_user_profile(self):
        """Load user profile from disk"""
        if self.user_file.exists():
            with open(self.user_file, 'r') as f:
                profile = json.load(f)
                # Ensure 'id' field exists
                if 'id' not in profile:
                    profile['id'] = 'local-user'
                return profile
        
        # Default profile for new users
        return {
            'id': 'local-user',
            'username': 'Guest',
            'housen_stage': 1,
            'housen_substage': 1,
            'journeys_completed': 0,
            'total_time_seconds': 0,
            'museum_visits': 0,
            'created_at': datetime.now().isoformat()
        }
    
    def save_user_profile(self, profile):
        """Save user profile to disk"""
        profile['last_updated'] = datetime.now().isoformat()
        with open(self.user_file, 'w') as f:
            json.dump(profile, f, indent=2)
    
    def save_journey(self, user_id, journey):
        """Save a journey to disk"""
        journey_id = journey['id']
        journey_file = self.journeys_dir / f"{user_id}_{journey_id}.json"
        
        journey['saved_at'] = datetime.now().isoformat()
        
        with open(journey_file, 'w') as f:
            json.dump(journey, f, indent=2)
    
    def load_journey(self, user_id, journey_id):
        """Load a specific journey"""
        journey_file = self.journeys_dir / f"{user_id}_{journey_id}.json"
        
        if journey_file.exists():
            with open(journey_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def get_all_journeys(self, user_id):
        """Get all journeys for a user"""
        journeys = []
        
        for journey_file in self.journeys_dir.glob(f"{user_id}_*.json"):
            with open(journey_file, 'r') as f:
                journey = json.load(f)
                journeys.append(journey)
        
        # Sort by date, newest first
        journeys.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
        
        return journeys
    
    def save_reflection(self, user_id, journey_id, reflection):
        """Save reflection responses"""
        reflection_file = self.reflections_dir / f"{user_id}_{journey_id}.json"
        
        reflection['saved_at'] = datetime.now().isoformat()
        
        with open(reflection_file, 'w') as f:
            json.dump(reflection, f, indent=2)
    
    def load_reflection(self, user_id, journey_id):
        """Load reflection for a journey"""
        reflection_file = self.reflections_dir / f"{user_id}_{journey_id}.json"
        
        if reflection_file.exists():
            with open(reflection_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def get_user_stats(self, user_id):
        """Get user statistics"""
        journeys = self.get_all_journeys(user_id)
        
        total_time = 0
        museum_visits = 0
        
        for journey in journeys:
            if 'completion_time' in journey:
                total_time += journey.get('completion_time', 0)
            if journey.get('at_museum', False):
                museum_visits += 1
        
        return {
            'total_journeys': len(journeys),
            'total_minutes': total_time // 60,
            'museum_visits': museum_visits
        }
    
    def get_constellation_data(self, user_profile, seed_artworks):
        """Get data for constellation visualization"""
        
        # Companion star (center) - represents the user
        companion_star = {
            'stage': user_profile.get('housen_stage', 1),
            'substage': user_profile.get('housen_substage', 1)
        }
        
        # Get user's completed journeys
        user_id = user_profile.get('id', 'local-user')
        journeys = self.get_all_journeys(user_id)
        
        # Only show seed artworks if user has completed fewer than 10 journeys
        show_seeds = len(journeys) < 10
        
        # Format journey data for constellation
        journey_data = []
        for journey in journeys:
            journey_data.append({
                'id': journey.get('id'),
                'title': journey.get('title', 'Untitled'),
                'artist': journey.get('artist', 'Unknown'),
                'stage': journey.get('stage', 1),
                'completed_at': journey.get('completed_at')
            })
        
        return {
            'companion_star': companion_star,
            'journey_count': len(journeys),
            'journeys': journey_data,
            'seed_artworks': seed_artworks if show_seeds else [],
            'show_seeds': show_seeds
        }