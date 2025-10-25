"""
User Assessment Engine
Tracks user progress through Housen stages and provides personalized feedback
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class UserAssessment:
    """Assesses user responses and tracks Housen stage progression"""
    
    def __init__(self):
        self.growth_indicators = self._load_growth_indicators()
        self.stage_descriptions = self._load_stage_descriptions()
    
    def assess_responses(self, responses: Dict, journey: Dict, current_stage: int, current_substage: int) -> Dict:
        """
        Assess user's reflection responses and determine stage progression
        
        Returns:
            Dict with assessment results including new stage/substage
        """
        
        # Analyze responses against growth indicators
        scores = self._analyze_responses(responses, current_stage)
        
        # Calculate overall quality score
        quality_score = self._calculate_quality_score(scores, current_stage)
        
        # Determine progression
        new_stage, new_substage, change = self._determine_progression(
            scores, quality_score, current_stage, current_substage
        )
        
        # Generate feedback
        feedback = self._generate_feedback(scores, change, new_stage, new_substage)
        
        return {
            "new_stage": new_stage,
            "new_substage": new_substage,
            "change": change,
            "quality_score": quality_score,
            "scores": scores,
            "feedback": feedback
        }
    
    def _analyze_responses(self, responses: Dict, stage: int) -> Dict:
        """Analyze responses against growth indicators for current stage"""
        
        scores = {}
        
        for activity_id, response in responses.items():
            if not response or len(response.strip()) < 10:
                continue
                
            # Get growth indicators for this stage
            indicators = self.growth_indicators.get(stage, {})
            
            # Simple keyword and length analysis
            response_lower = response.lower()
            word_count = len(response.split())
            
            # Stage-specific analysis
            if stage == 1:  # Accountive
                scores[activity_id] = {
                    "personal_connection": self._score_personal_connection(response_lower),
                    "emotional_engagement": self._score_emotional_engagement(response_lower),
                    "storytelling": self._score_storytelling(response_lower, word_count)
                }
            elif stage == 2:  # Constructive
                scores[activity_id] = {
                    "observational_detail": self._score_observational_detail(response_lower, word_count),
                    "descriptive_language": self._score_descriptive_language(response_lower),
                    "pattern_recognition": self._score_pattern_recognition(response_lower)
                }
            elif stage == 3:  # Classifying
                scores[activity_id] = {
                    "analytical_thinking": self._score_analytical_thinking(response_lower),
                    "technique_awareness": self._score_technique_awareness(response_lower),
                    "interpretation_attempts": self._score_interpretation_attempts(response_lower)
                }
            elif stage == 4:  # Interpretive
                scores[activity_id] = {
                    "multiple_perspectives": self._score_multiple_perspectives(response_lower),
                    "contextual_thinking": self._score_contextual_thinking(response_lower),
                    "sophisticated_analysis": self._score_sophisticated_analysis(response_lower, word_count)
                }
            elif stage == 5:  # Re-creative
                scores[activity_id] = {
                    "philosophical_thinking": self._score_philosophical_thinking(response_lower),
                    "metacognitive_awareness": self._score_metacognitive_awareness(response_lower),
                    "synthesis": self._score_synthesis(response_lower, word_count)
                }
        
        return scores
    
    def _calculate_quality_score(self, scores: Dict, stage: int) -> float:
        """Calculate overall quality score from individual scores"""
        if not scores:
            return 50.0
        
        all_scores = []
        for activity_scores in scores.values():
            all_scores.extend(activity_scores.values())
        
        if not all_scores:
            return 50.0
        
        # Weight recent activities more heavily
        avg_score = sum(all_scores) / len(all_scores)
        
        # Adjust for stage difficulty
        stage_adjustment = {
            1: 1.0,   # No adjustment for stage 1
            2: 0.95,  # Slightly harder
            3: 0.90,  # Harder
            4: 0.85,  # Much harder
            5: 0.80   # Hardest
        }
        
        adjusted_score = avg_score * stage_adjustment.get(stage, 1.0)
        return min(100.0, max(0.0, adjusted_score))
    
    def _determine_progression(self, scores: Dict, quality_score: float, current_stage: int, current_substage: int) -> Tuple[int, int, str]:
        """Determine if user should progress to next stage/substage"""
        
        # Progression thresholds
        progression_threshold = 75.0
        regression_threshold = 40.0
        
        if quality_score >= progression_threshold:
            # Check if ready for next stage
            if current_substage >= 3 and current_stage < 5:
                return current_stage + 1, 1, "progression"
            elif current_substage < 3:
                return current_stage, current_substage + 1, "progression"
            else:
                return current_stage, current_substage, "maintenance"
        
        elif quality_score <= regression_threshold:
            # Check for regression
            if current_substage > 1:
                return current_stage, current_substage - 1, "regression"
            elif current_stage > 1:
                return current_stage - 1, 3, "regression"
            else:
                return current_stage, current_substage, "maintenance"
        
        else:
            return current_stage, current_substage, "maintenance"
    
    def _generate_feedback(self, scores: Dict, change: str, new_stage: int, new_substage: int) -> str:
        """Generate personalized feedback based on assessment"""
        
        if change == "progression":
            if new_stage > 1:
                return f"Congratulations! You've reached Housen Stage {new_stage}. Your observations are becoming more sophisticated and analytical."
            else:
                return f"Great progress! You're advancing to substage {new_substage} of Stage {new_stage}. Keep building on your observational skills."
        
        elif change == "regression":
            return "Don't worry - learning isn't always linear. Take your time and focus on the fundamentals. You'll get back on track."
        
        else:
            return "You're doing well at your current level. Keep practicing and challenging yourself with new observations."
    
    def _score_personal_connection(self, response: str) -> float:
        """Score personal connection indicators"""
        personal_words = ["i", "me", "my", "myself", "reminds me", "feel", "remember", "experience"]
        score = sum(1 for word in personal_words if word in response) * 15
        return min(100, score)
    
    def _score_emotional_engagement(self, response: str) -> float:
        """Score emotional engagement indicators"""
        emotion_words = ["feel", "emotion", "mood", "atmosphere", "beautiful", "powerful", "moving", "striking"]
        score = sum(1 for word in emotion_words if word in response) * 12
        return min(100, score)
    
    def _score_storytelling(self, response: str, word_count: int) -> float:
        """Score storytelling ability"""
        story_words = ["story", "narrative", "happening", "scene", "character", "plot", "beginning", "end"]
        story_score = sum(1 for word in story_words if word in response) * 10
        length_score = min(50, word_count * 2)
        return min(100, story_score + length_score)
    
    def _score_observational_detail(self, response: str, word_count: int) -> float:
        """Score observational detail"""
        detail_words = ["notice", "see", "observe", "detail", "specific", "particular", "exactly", "precisely"]
        detail_score = sum(1 for word in detail_words if word in response) * 8
        length_score = min(40, word_count * 1.5)
        return min(100, detail_score + length_score)
    
    def _score_descriptive_language(self, response: str) -> float:
        """Score descriptive language use"""
        descriptive_words = ["color", "shape", "line", "texture", "bright", "dark", "large", "small", "curved", "straight"]
        score = sum(1 for word in descriptive_words if word in response) * 6
        return min(100, score)
    
    def _score_pattern_recognition(self, response: str) -> float:
        """Score pattern recognition ability"""
        pattern_words = ["pattern", "repetition", "similar", "different", "compare", "contrast", "group", "category"]
        score = sum(1 for word in pattern_words if word in response) * 10
        return min(100, score)
    
    def _score_analytical_thinking(self, response: str) -> float:
        """Score analytical thinking"""
        analytical_words = ["because", "why", "how", "analysis", "think", "consider", "reason", "logic"]
        score = sum(1 for word in analytical_words if word in response) * 8
        return min(100, score)
    
    def _score_technique_awareness(self, response: str) -> float:
        """Score technique awareness"""
        technique_words = ["technique", "method", "created", "made", "brush", "paint", "canvas", "sculpture"]
        score = sum(1 for word in technique_words if word in response) * 10
        return min(100, score)
    
    def _score_interpretation_attempts(self, response: str) -> float:
        """Score interpretation attempts"""
        interpret_words = ["means", "represents", "symbol", "meaning", "interpret", "suggests", "implies", "signifies"]
        score = sum(1 for word in interpret_words if word in response) * 8
        return min(100, score)
    
    def _score_multiple_perspectives(self, response: str) -> float:
        """Score multiple perspectives thinking"""
        perspective_words = ["perspective", "viewpoint", "different", "another", "alternative", "could", "might", "possible"]
        score = sum(1 for word in perspective_words if word in response) * 7
        return min(100, score)
    
    def _score_contextual_thinking(self, response: str) -> float:
        """Score contextual thinking"""
        context_words = ["context", "history", "period", "time", "culture", "society", "tradition", "influence"]
        score = sum(1 for word in context_words if word in response) * 8
        return min(100, score)
    
    def _score_sophisticated_analysis(self, response: str, word_count: int) -> float:
        """Score sophisticated analysis"""
        sophisticated_words = ["complex", "nuanced", "layered", "multifaceted", "sophisticated", "intricate", "subtle"]
        sophisticated_score = sum(1 for word in sophisticated_words if word in response) * 10
        complexity_score = min(50, word_count * 0.8)
        return min(100, sophisticated_score + complexity_score)
    
    def _score_philosophical_thinking(self, response: str) -> float:
        """Score philosophical thinking"""
        philosophical_words = ["philosophy", "existential", "universal", "human", "nature", "reality", "truth", "meaning"]
        score = sum(1 for word in philosophical_words if word in response) * 8
        return min(100, score)
    
    def _score_metacognitive_awareness(self, response: str) -> float:
        """Score metacognitive awareness"""
        meta_words = ["aware", "conscious", "realize", "understand", "process", "thinking", "reflection", "insight"]
        score = sum(1 for word in meta_words if word in response) * 7
        return min(100, score)
    
    def _score_synthesis(self, response: str, word_count: int) -> float:
        """Score synthesis ability"""
        synthesis_words = ["connect", "synthesize", "integrate", "combine", "unify", "whole", "together", "relationship"]
        synthesis_score = sum(1 for word in synthesis_words if word in response) * 8
        complexity_score = min(40, word_count * 0.6)
        return min(100, synthesis_score + complexity_score)
    
    def _load_growth_indicators(self) -> Dict:
        """Load growth indicators for each Housen stage"""
        return {
            1: {
                "personal_connection": "Ability to connect artwork to personal experience",
                "emotional_engagement": "Emotional response and engagement",
                "storytelling": "Narrative thinking and story creation"
            },
            2: {
                "observational_detail": "Quantity and quality of observations",
                "descriptive_language": "Use of descriptive vocabulary",
                "pattern_recognition": "Ability to identify patterns and relationships"
            },
            3: {
                "analytical_thinking": "Logical analysis and reasoning",
                "technique_awareness": "Understanding of artistic techniques",
                "interpretation_attempts": "Attempts at meaning-making"
            },
            4: {
                "multiple_perspectives": "Consideration of different viewpoints",
                "contextual_thinking": "Historical and cultural awareness",
                "sophisticated_analysis": "Complex, nuanced analysis"
            },
            5: {
                "philosophical_thinking": "Engagement with universal questions",
                "metacognitive_awareness": "Self-awareness of thinking process",
                "synthesis": "Integration of multiple ideas and perspectives"
            }
        }
    
    def _load_stage_descriptions(self) -> Dict:
        """Load descriptions for each Housen stage"""
        return {
            1: {
                "name": "Accountive",
                "description": "You focus on personal connections and storytelling. You see art through your own experiences and emotions.",
                "characteristics": ["Personal connections", "Emotional responses", "Storytelling", "Concrete observations"]
            },
            2: {
                "name": "Constructive",
                "description": "You're building observational skills and noticing details. You describe what you see systematically.",
                "characteristics": ["Detailed observation", "Descriptive language", "Pattern recognition", "Visual analysis"]
            },
            3: {
                "name": "Classifying",
                "description": "You think analytically about technique and meaning. You consider how artworks are made and what they might represent.",
                "characteristics": ["Analytical thinking", "Technique awareness", "Interpretation attempts", "Logical reasoning"]
            },
            4: {
                "name": "Interpretive",
                "description": "You explore multiple meanings and consider historical context. You engage with sophisticated analysis.",
                "characteristics": ["Multiple perspectives", "Contextual thinking", "Sophisticated analysis", "Cultural awareness"]
            },
            5: {
                "name": "Re-creative",
                "description": "You engage with complex philosophical questions and demonstrate metacognitive awareness.",
                "characteristics": ["Philosophical thinking", "Metacognitive awareness", "Synthesis", "Universal questions"]
            }
        }
    
    def get_stage_description(self, stage: int, substage: int) -> Dict:
        """Get description for current stage and substage"""
        stage_info = self.stage_descriptions.get(stage, self.stage_descriptions[1])
        
        substage_names = {
            1: "Early",
            2: "Developing", 
            3: "Advanced"
        }
        
        return {
            "stage": stage,
            "substage": substage,
            "name": stage_info["name"],
            "substage_name": substage_names.get(substage, "Unknown"),
            "description": stage_info["description"],
            "characteristics": stage_info["characteristics"]
        }
    
    def get_notifications(self, user_profile: Dict) -> List[Dict]:
        """Get notifications for user based on their profile"""
        notifications = []
        
        # Check for stage progression
        if user_profile.get('stage_history'):
            latest_change = user_profile['stage_history'][-1]
            if latest_change.get('change') == 'progression':
                notifications.append({
                    "type": "achievement",
                    "title": "Stage Progression!",
                    "message": f"You've advanced to Stage {latest_change['stage']}",
                    "icon": "🎉"
                })
        
        # Check for new badges
        recent_achievements = user_profile.get('achievements', [])
        if recent_achievements:
            latest_achievement = recent_achievements[-1]
            if latest_achievement.get('earned_at'):
                earned_date = datetime.fromisoformat(latest_achievement['earned_at'])
                if (datetime.now() - earned_date).days < 1:  # Within last day
                    notifications.append({
                        "type": "badge",
                        "title": "New Badge Earned!",
                        "message": latest_achievement['name'],
                        "icon": latest_achievement.get('icon', '🏆')
                    })
        
        return notifications
    
    def calculate_streak(self, user_profile: Dict) -> int:
        """Calculate current engagement streak"""
        if not user_profile.get('last_activity'):
            return 0
        
        last_activity = datetime.fromisoformat(user_profile['last_activity'])
        days_since = (datetime.now() - last_activity).days
        
        if days_since == 0:
            return 1
        elif days_since == 1:
            return user_profile.get('current_streak', 0) + 1
        else:
            return 0
    
    def check_inactivity_regression(self, user_profile: Dict) -> bool:
        """Check if user should regress due to inactivity"""
        if not user_profile.get('last_activity'):
            return False
        
        last_activity = datetime.fromisoformat(user_profile['last_activity'])
        days_inactive = (datetime.now() - last_activity).days
        
        # Regress after 30 days of inactivity
        if days_inactive >= 30:
            current_stage = user_profile['housen_stage']
            current_substage = user_profile['housen_substage']
            
            if current_substage > 1:
                user_profile['housen_substage'] = current_substage - 1
            elif current_stage > 1:
                user_profile['housen_stage'] = current_stage - 1
                user_profile['housen_substage'] = 3
            
            user_profile['stage_history'].append({
                'date': datetime.now().isoformat(),
                'stage': f"{user_profile['housen_stage']}.{user_profile['housen_substage']}",
                'change': 'regression'
            })
            
            return True
        
        return False
