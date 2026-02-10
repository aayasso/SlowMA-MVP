"""
SlowMA Activity Generator
AI-powered generation of personalized reflection activities using Anthropic Claude.
"""

import os
from typing import List
from anthropic import Anthropic
from app.models.schemas import ReflectionActivity, ActivityType


class ActivityGenerator:
    """
    Generates personalized reflection activities based on:
    - User's Housen stage and substage
    - Artwork characteristics (later: will analyze image)
    - Context (museum visit vs. home observation)
    """
    
    def __init__(self):
        """Initialize Anthropic client."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found in environment variables. "
                "Add it to your .env file."
            )
        self.client = Anthropic(api_key=api_key)
    
    
    def generate_activities(
        self,
        housen_stage: int,
        housen_substage: int,
        at_museum: bool = False,
        artwork_context: dict = None
    ) -> List[ReflectionActivity]:
        """
        Generate 3 personalized reflection activities.
        
        Args:
            housen_stage: User's current Housen stage (1-5)
            housen_substage: User's substage (1-3: Early, Developing, Advanced)
            at_museum: Whether user is at a museum
            artwork_context: Optional artwork details (title, artist, style, etc.)
        
        Returns:
            List of 3 ReflectionActivity objects
        """
        
        # Build prompt for Claude
        prompt = self._build_prompt(
            housen_stage, 
            housen_substage, 
            at_museum, 
            artwork_context
        )
        
        try:
            # Call Anthropic API
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse response into activities
            activities = self._parse_response(message.content[0].text)
            
            return activities
            
        except Exception as e:
            print(f"Error generating activities: {e}")
            # Fall back to simple activities if API fails
            return self._fallback_activities(housen_stage)
    
    
    def _build_prompt(
        self,
        housen_stage: int,
        housen_substage: int,
        at_museum: bool,
        artwork_context: dict
    ) -> str:
        """Build the prompt for Claude API."""
        
        # Stage descriptions
        stage_info = {
            1: {
                "name": "Accountive",
                "description": "Concrete, observational. Uses personal associations and storytelling.",
                "focus": "What they see, colors, shapes, immediate emotional reactions"
            },
            2: {
                "name": "Constructive",
                "description": "Building own interpretations. Creating narratives and meanings.",
                "focus": "Stories, personal connections, constructing meaning"
            },
            3: {
                "name": "Classifying",
                "description": "Analytical, using art historical knowledge. Categorizing and comparing.",
                "focus": "Style, technique, art historical context, comparisons"
            },
            4: {
                "name": "Interpretive",
                "description": "Balancing personal response with formal analysis. Multiple perspectives.",
                "focus": "Synthesis of feeling and thinking, multiple interpretations"
            },
            5: {
                "name": "Re-creative",
                "description": "Deep engagement, re-experiencing artist's creative process.",
                "focus": "Empathy with artist, understanding creative choices deeply"
            }
        }
        
        substage_info = {
            1: "Early - Just beginning at this stage",
            2: "Developing - Growing capabilities at this stage", 
            3: "Advanced - Mastering this stage, ready for next"
        }
        
        current_stage = stage_info[housen_stage]
        current_substage = substage_info[housen_substage]
        
        # Build context about artwork
        artwork_desc = "an artwork the user just observed"
        if artwork_context:
            if artwork_context.get("title"):
                artwork_desc = f"'{artwork_context['title']}'"
            if artwork_context.get("artist"):
                artwork_desc += f" by {artwork_context['artist']}"
        
        location = "at a museum" if at_museum else "at home or a gallery"
        
        prompt = f"""You are an expert art educator creating reflection activities for SlowMA, an app teaching visual literacy through slow looking.

CONTEXT:
- User just observed {artwork_desc}
- Location: {location}
- User's Housen Stage: {housen_stage} - {current_stage['name']}
- Substage: {current_substage}
- Stage Description: {current_stage['description']}
- Stage Focus: {current_stage['focus']}

TASK:
Generate exactly 3 reflection activities that:
1. Match the user's developmental stage
2. Help them practice skills at their current level
3. Gently stretch them toward the next stage
4. Feel personal, not academic
5. Use encouraging, Duolingo-style tone

ACTIVITY TYPES (choose 3 different types):
- TEXT: Open-ended written reflection
- COMPARISON: Compare with other art or experiences  
- CONNECTION: Connect to personal life or memories
- CREATIVE: Draw, imagine, or create something
- SYNTHESIS: Pull together multiple observations

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
---
ACTIVITY 1
Type: [TEXT/COMPARISON/CONNECTION/CREATIVE/SYNTHESIS]
Title: [Short, inviting title - max 6 words]
Prompt: [The main question or instruction - 1-2 sentences]
Placeholder: [Example response start - shows them how to begin]
Why: [One sentence explaining the pedagogical value]
---
ACTIVITY 2
Type: [different type from Activity 1]
Title: [Short, inviting title]
Prompt: [The main question]
Placeholder: [Example response start]
Why: [Pedagogical explanation]
---
ACTIVITY 3
Type: [different type from Activities 1 and 2]
Title: [Short, inviting title]
Prompt: [The main question]
Placeholder: [Example response start]
Why: [Pedagogical explanation]
---

IMPORTANT GUIDELINES:
- Use warm, encouraging language ("Notice...", "What stands out...", "Describe...")
- Avoid art jargon unless user is Stage 3+
- Keep prompts judgment-free (no "good" or "bad" art)
- Make placeholders feel natural, not intimidating
- Activities should build on each other subtly

Generate the 3 activities now:"""
        
        return prompt
    
    
    def _parse_response(self, response_text: str) -> List[ReflectionActivity]:
        """Parse Claude's response into ReflectionActivity objects."""
        
        activities = []
        
        # Split by "---" separators
        sections = [s.strip() for s in response_text.split("---") if s.strip()]
        
        activity_id = 1
        for section in sections:
            if not section.startswith("ACTIVITY"):
                continue
            
            lines = section.split("\n")
            activity_data = {}
            
            for line in lines:
                line = line.strip()
                if line.startswith("Type:"):
                    type_str = line.replace("Type:", "").strip().upper()
                    activity_data["type"] = type_str
                elif line.startswith("Title:"):
                    activity_data["title"] = line.replace("Title:", "").strip()
                elif line.startswith("Prompt:"):
                    activity_data["prompt"] = line.replace("Prompt:", "").strip()
                elif line.startswith("Placeholder:"):
                    activity_data["placeholder"] = line.replace("Placeholder:", "").strip()
                elif line.startswith("Why:"):
                    activity_data["why"] = line.replace("Why:", "").strip()
            
            # Create activity if we have all required fields
            if all(k in activity_data for k in ["type", "title", "prompt"]):
                try:
                    activity = ReflectionActivity(
                        id=f"activity_{activity_id}",
                        type=ActivityType(activity_data["type"].lower()),
                        title=activity_data["title"],
                        prompt=activity_data["prompt"],
                        placeholder=activity_data.get("placeholder"),
                        why_this_activity=activity_data.get("why")
                    )
                    activities.append(activity)
                    activity_id += 1
                except (ValueError, KeyError) as e:
                    print(f"Error parsing activity: {e}")
                    continue
        
        # If parsing failed, use fallback
        if len(activities) < 3:
            print("Warning: Could not parse 3 activities from response, using fallback")
            return self._fallback_activities(1)
        
        return activities[:3]  # Return first 3
    
    
    def _fallback_activities(self, housen_stage: int) -> List[ReflectionActivity]:
        """
        Fallback activities if API fails.
        Simple, safe activities that work for any stage.
        """
        return [
            ReflectionActivity(
                id="activity_1",
                type=ActivityType.TEXT,
                title="What caught your eye?",
                prompt="Describe what you noticed first when you looked at this artwork.",
                placeholder="The first thing I noticed was...",
                why_this_activity="Focusing on initial impressions builds observation skills."
            ),
            ReflectionActivity(
                id="activity_2",
                type=ActivityType.CONNECTION,
                title="Personal connection",
                prompt="Does this artwork remind you of anything in your own life?",
                placeholder="This reminds me of...",
                why_this_activity="Making personal connections deepens engagement with art."
            ),
            ReflectionActivity(
                id="activity_3",
                type=ActivityType.TEXT,
                title="One word",
                prompt="If you had to describe this artwork in one word, what would it be and why?",
                placeholder="I would choose the word...",
                why_this_activity="Distilling observations into a single word requires synthesis."
            )
        ]


# Create singleton instance
_generator = None

def get_activity_generator() -> ActivityGenerator:
    """Get or create the ActivityGenerator singleton."""
    global _generator
    if _generator is None:
        _generator = ActivityGenerator()
    return _generator