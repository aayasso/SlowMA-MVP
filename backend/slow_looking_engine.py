"""
Slow Looking Engine
Enhanced Claude integration with Housen stage awareness and Unified Framework
"""

import os
import json
import base64
import hashlib
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class SlowLookingEngine:
    """Creates personalized slow looking journeys based on user's Housen stage"""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env file")
        
        self.client = Anthropic(api_key=self.api_key)
        self.cache_dir = Path("data/journey_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def create_journey(self, image_path: Path, housen_stage: int = 1, housen_substage: int = 1):
        """
        Create a personalized slow looking journey
        
        Args:
            image_path: Path to artwork image
            housen_stage: User's current Housen stage (1-5)
            housen_substage: User's current substage (1-3)
            
        Returns:
            Complete journey data structure
        """
        
        # Check cache first
        cache_key = self._get_cache_key(image_path, housen_stage, housen_substage)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            print(f"Using cached journey for {image_path.name}")
            return json.loads(cache_file.read_text())
        
        print(f"Creating personalized journey for {image_path.name}")
        print(f"  User level: Stage {housen_stage}.{housen_substage}")
        
        # Encode image
        media_type, image_data = self._encode_image(image_path)
        
        # Get personalized prompt
        prompt = self._create_housen_aware_prompt(housen_stage, housen_substage)
        
        # Call Claude API
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )
            
            # Parse response
            response_text = response.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            journey_data = json.loads(response_text.strip())
            
            # Add metadata
            journey_data["image_filename"] = image_path.name
            journey_data["created_at"] = datetime.now().isoformat()
            journey_data["housen_stage"] = housen_stage
            journey_data["housen_substage"] = housen_substage
            
            # Cache the result
            cache_file.write_text(json.dumps(journey_data, indent=2))
            
            print(f"✓ Journey created: {journey_data['total_steps']} steps")
            
            return journey_data
            
        except Exception as e:
            print(f"Error creating journey: {e}")
            raise
    
    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        """Encode image to base64"""
        suffix = image_path.suffix.lower()
        media_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        media_type = media_type_map.get(suffix, "image/jpeg")
        image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
        return media_type, image_data
    
    def _get_cache_key(self, image_path: Path, stage: int, substage: int) -> str:
        """Generate cache key from image and user level"""
        image_hash = hashlib.md5(image_path.read_bytes()).hexdigest()
        return f"{image_hash}_s{stage}_{substage}"
    
    def _create_housen_aware_prompt(self, stage: int, substage: int) -> str:
        """
        Create a prompt tailored to user's Housen stage
        Based on the Unified Framework and Housen's Aesthetic Development stages
        """
        
        # Define characteristics for each stage
        stage_characteristics = {
            1: {
                "focus": "Personal connections, storytelling, concrete observations",
                "approach": "Use simple, vivid language. Connect to everyday experiences. Encourage emotional responses.",
                "avoid": "Art historical terminology, complex analysis, abstract concepts",
                "prompts": "What does this remind you of? How does it make you feel? What's happening in this image?"
            },
            2: {
                "focus": "Building observational skills, noticing details, describing what's visible",
                "approach": "Guide systematic observation. Ask about specific visual elements. Build vocabulary naturally.",
                "avoid": "Rushing to meaning, heavy interpretation, overly technical language",
                "prompts": "What do you notice about the colors? How are things arranged? What draws your eye?"
            },
            3: {
                "focus": "Analytical thinking, considering technique, beginning interpretation",
                "approach": "Encourage thinking about how it was made. Introduce concepts gently. Multiple perspectives.",
                "avoid": "Definitive interpretations, dismissing personal response, too much information at once",
                "prompts": "How do you think this was created? What choices did the artist make? What might this represent?"
            },
            4: {
                "focus": "Historical context, artistic movements, deeper interpretation",
                "approach": "Integrate context naturally. Discuss multiple meanings. Encourage sophisticated analysis.",
                "avoid": "Lecturing, assuming knowledge, discouraging personal interpretation",
                "prompts": "How does this relate to its time? What artistic traditions influenced this? What layers of meaning do you see?"
            },
            5: {
                "focus": "Complex synthesis, personal philosophy, metacognitive awareness",
                "approach": "Engage in dialogue. Explore ambiguity. Connect to broader questions.",
                "avoid": "Oversimplifying, providing all answers, limiting inquiry",
                "prompts": "What questions does this raise? How does this challenge conventions? What's your relationship to this work?"
            }
        }
        
        stage_info = stage_characteristics.get(stage, stage_characteristics[1])
        
        # Adjust based on substage (1=early, 2=mid, 3=advanced within stage)
        substage_modifier = {
            1: "Focus on the fundamentals of this stage. Be more supportive and explanatory.",
            2: "Balance support with challenge. User is developing confidence at this stage.",
            3: "Push toward next stage characteristics. User is ready for more complexity."
        }
        
        modifier = substage_modifier.get(substage, substage_modifier[1])
        
        return f"""You are an art educator creating a personalized "slow looking" experience for someone standing in front of an artwork.

USER'S CURRENT LEVEL: Housen Stage {stage}.{substage}

STAGE {stage} CHARACTERISTICS:
- Focus: {stage_info['focus']}
- Approach: {stage_info['approach']}
- Avoid: {stage_info['avoid']}
- Good prompts: {stage_info['prompts']}

SUBSTAGE MODIFIER: {modifier}

YOUR GOAL: Help this user grow to the next level while meeting them where they are.

UNIFIED FRAMEWORK PRINCIPLES:
1. Deferred Judgment: Don't rush to conclusions. Let discovery unfold.
2. Multi-perspectival Awareness: Show how things appear different from various angles.
3. Active Construction: Engage them in meaning-making, not passive reception.
4. Transfer Potential: Build skills that work beyond this single artwork.

CRITICAL TONE REQUIREMENTS:
- Educational, informative, edifying
- NEVER intimidating or pretentious
- Gently provoke mindful analysis
- Encourage engagement and synthesis
- Be supportive like Duolingo
- Focus on helping them SEE, not memorizing facts

WALKTHROUGH STRUCTURE (3-6 steps):
- Choose step count based on artwork complexity
- Simpler works: 3-4 steps
- Rich, complex works: 5-6 steps
- Each step builds on previous observations

FOR EACH STEP:
1. Look-away time (30-60 seconds):
   - Longer for complex observations (50-60s)
   - Shorter for immediate elements (30-45s)
   - First step often longest to help them settle

2. Soft prompt (during look-away):
   - Gentle, contemplative guidance
   - Open-ended questions
   - Help them see without directing
   - Match their Housen stage level

3. Observation reveal:
   - What to notice (accessible, specific)
   - Why it matters (connect to their level)
   - Use "Notice..." or "See how..." language
   - Natural, conversational tone

4. Bounding box:
   - Normalized coordinates (0-1)
   - Highlight genuinely meaningful areas
   - Mix overall composition + intimate details

PEDAGOGICAL SEQUENCING:
Order observations to create a narrative arc appropriate for their stage:
- Stage 1: Emotional → Personal → Story
- Stage 2: Obvious → Details → Patterns
- Stage 3: Technique → Composition → Meaning
- Stage 4: Context → Interpretation → Significance  
- Stage 5: Questions → Complexity → Philosophy

RESPONSE FORMAT (valid JSON):
{{
    "journey_id": "auto-generated-uuid",
    "artwork": {{
        "title": "title or null",
        "artist": "artist or null",
        "year": "year or null",
        "period": "period or null",
        "style": "style or null"
    }},
    "total_steps": 3-6,
    "estimated_duration_minutes": 3-8,
    "steps": [
        {{
            "step_number": 1,
            "region": {{
                "x": 0.0-1.0,
                "y": 0.0-1.0,
                "width": 0.0-1.0,
                "height": 0.0-1.0,
                "title": "Brief title (max 40 chars)",
                "observation": "What to notice (80-250 chars, match their level)",
                "why_notable": "Why this matters (50-200 chars, accessible)",
                "soft_prompt": "Gentle guidance (max 100 chars)",
                "concept_tag": "composition|technique|symbolism|color|light|subject|emotion|context|style"
            }},
            "look_away_duration": 30-60,
            "why_this_sequence": "Why now? (max 150 chars)",
            "builds_on": "Connection to previous or null (max 200 chars)"
        }}
    ],
    "welcome_text": "Warm invitation (max 200 chars, match their level)",
    "final_summary": {{
        "main_takeaway": "Key insight (100-300 chars)",
        "connections": "How observations connect (150-400 chars)",
        "invitation_to_return": "Encouraging close (max 150 chars)",
        "reflection_question": "Open question (max 100 chars)"
    }},
    "confidence_score": 0.0-1.0,
    "pedagogical_approach": "Strategy used (max 200 chars)"
}}

Remember: You're not teaching art history facts. You're teaching them how to LOOK and SEE. Make it personal, accessible, and growth-oriented for their specific stage."""
    
    def get_stage_name(self, stage: int) -> str:
        """Get human-readable name for Housen stage"""
        names = {
            1: "Accountive",
            2: "Constructive", 
            3: "Classifying",
            4: "Interpretive",
            5: "Re-creative"
        }
        return names.get(stage, "Unknown")
