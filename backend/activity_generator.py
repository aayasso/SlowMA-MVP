"""
Reflection Activity Generator
Creates personalized reflection/extension activities based on journey and user level
"""

import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class ActivityGenerator:
    """Generates personalized reflection activities"""
    
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
    
    def generate_activities(self, journey: dict, housen_stage: int, housen_substage: int) -> list:
        """
        Generate 2-4 reflection activities tailored to user's level
        
        Activities can be any format that allows assessment:
        - Open-ended text questions
        - Comparative analysis
        - Creative responses
        - Observation tasks
        - Synthesis exercises
        """
        
        if not self.client:
            return self._fallback_activities(housen_stage, housen_substage)
        
        prompt = self._create_activity_prompt(journey, housen_stage, housen_substage)
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3072,
                temperature=0.8,  # Higher for creative activity generation
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = response.content[0].text
            
            # Extract JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            activities = json.loads(response_text.strip())
            return activities.get('activities', [])
            
        except Exception as e:
            print(f"Error generating activities: {e}")
            return self._fallback_activities(housen_stage, housen_substage)
    
    def _create_activity_prompt(self, journey: dict, stage: int, substage: int) -> str:
        """Create prompt for activity generation"""
        
        artwork_title = journey.get('artwork', {}).get('title', 'this artwork')
        artist = journey.get('artwork', {}).get('artist', 'the artist')
        
        return f"""You are creating personalized reflection activities after a slow looking experience.

ARTWORK: {artwork_title} by {artist}

USER LEVEL: Housen Stage {stage}.{substage}

JOURNEY SUMMARY:
{json.dumps(journey.get('final_summary', {}), indent=2)}

STAGE {stage} CHARACTERISTICS:
{self._get_stage_guidance(stage)}

SUBSTAGE {substage}:
{self._get_substage_guidance(substage)}

YOUR TASK:
Create 2-4 reflection activities that:
1. Match the user's current level
2. Gently push toward growth
3. Allow you to assess their responses against Growth Indicators
4. Are engaging and not intimidating
5. Connect to the journey they just experienced

ACTIVITY TYPES YOU CAN USE:
- Open-ended questions (text response)
- Comparative thinking ("How is this similar/different to...")
- Personal connection ("What does this remind you of...")
- Creative response ("Draw/describe...")
- Evidence-based ("What makes you say that?")
- Synthesis ("How do these observations connect?")
- Transfer ("How could you use this way of looking elsewhere?")

CRITICAL REQUIREMENTS:
- Educational and edifying, never intimidating
- Build on what they just discovered
- Progressive difficulty (easier to harder)
- Each activity should reveal something about their Growth Indicators

Return ONLY valid JSON:
{{
    "activities": [
        {{
            "id": "activity_1",
            "type": "text|comparison|connection|creative|synthesis",
            "title": "Brief engaging title (max 50 chars)",
            "prompt": "Clear, friendly instructions (100-300 chars)",
            "placeholder": "Helpful example or guidance (max 100 chars)",
            "why_this_activity": "What growth indicators this assesses (internal, max 150 chars)"
        }}
    ]
}}

Create 2-4 activities. Quality over quantity."""
    
    def _get_stage_guidance(self, stage: int) -> str:
        """Get guidance for activity generation based on stage"""
        guidance = {
            1: "Focus on personal connections, emotions, storytelling. Ask about feelings and memories. Keep it concrete and relatable.",
            2: "Encourage detailed observation and description. Ask what they see, compare elements, notice patterns. Build observational vocabulary.",
            3: "Prompt analytical thinking about technique and meaning. Ask how it was made, why certain choices, what it might represent.",
            4: "Explore multiple interpretations, context, symbolism. Ask about deeper meanings, historical significance, personal significance.",
            5: "Engage with complexity, ambiguity, universal questions. Ask philosophical questions, challenge assumptions, explore metacognition."
        }
        return guidance.get(stage, guidance[1])
    
    def _get_substage_guidance(self, substage: int) -> str:
        """Get guidance for substage"""
        guidance = {
            1: "Early in this stage - be supportive, scaffold heavily, celebrate small observations",
            2: "Developing - balance support and challenge, encourage independence, build confidence",
            3: "Advanced - ready for next level thinking, push boundaries, introduce new perspectives"
        }
        return guidance.get(substage, guidance[1])
    
    def _fallback_activities(self, stage: int, substage: int) -> list:
        """Fallback activities if API unavailable"""
        
        # Stage-appropriate fallback activities
        stage_activities = {
            1: [
                {
                    "id": "activity_1",
                    "type": "connection",
                    "title": "Personal Connection",
                    "prompt": "What does this artwork remind you of from your own life? It could be a place, person, feeling, or memory.",
                    "placeholder": "This reminds me of...",
                    "why_this_activity": "Assesses personal engagement and storytelling ability"
                },
                {
                    "id": "activity_2",
                    "type": "text",
                    "title": "Your Feelings",
                    "prompt": "How did looking slowly at this artwork make you feel? Why do you think it made you feel that way?",
                    "placeholder": "I felt...",
                    "why_this_activity": "Assesses emotional engagement and reflection"
                }
            ],
            2: [
                {
                    "id": "activity_1",
                    "type": "text",
                    "title": "Detailed Observation",
                    "prompt": "Describe three specific details you noticed during your slow look that you might have missed in a quick glance.",
                    "placeholder": "I noticed...",
                    "why_this_activity": "Assesses observational quantity and quality"
                },
                {
                    "id": "activity_2",
                    "type": "comparison",
                    "title": "Compare and Contrast",
                    "prompt": "Think of another artwork or image you know. How is this similar or different?",
                    "placeholder": "Compared to..., this artwork...",
                    "why_this_activity": "Assesses ability to make connections and comparisons"
                }
            ],
            3: [
                {
                    "id": "activity_1",
                    "type": "text",
                    "title": "Artist's Choices",
                    "prompt": "What choices do you think the artist made in creating this work? Why might they have made those choices?",
                    "placeholder": "The artist chose to...",
                    "why_this_activity": "Assesses analytical thinking about technique"
                },
                {
                    "id": "activity_2",
                    "type": "synthesis",
                    "title": "Connecting Ideas",
                    "prompt": "How do the different observations you made connect together? What larger idea or theme emerges?",
                    "placeholder": "These observations connect because...",
                    "why_this_activity": "Assesses ability to synthesize and find meaning"
                }
            ],
            4: [
                {
                    "id": "activity_1",
                    "type": "text",
                    "title": "Multiple Meanings",
                    "prompt": "What are two or three different ways someone might interpret this artwork? What evidence supports each interpretation?",
                    "placeholder": "One interpretation could be...",
                    "why_this_activity": "Assesses multiple perspectives and evidence-based thinking"
                },
                {
                    "id": "activity_2",
                    "type": "connection",
                    "title": "Personal Significance",
                    "prompt": "What does this artwork mean to you personally? How does it connect to your own experiences or beliefs?",
                    "placeholder": "This artwork speaks to me because...",
                    "why_this_activity": "Assesses personal interpretation and meaning-making"
                }
            ],
            5: [
                {
                    "id": "activity_1",
                    "type": "synthesis",
                    "title": "Deeper Questions",
                    "prompt": "What questions does this artwork raise about art, life, or human experience? Why do these questions matter?",
                    "placeholder": "This artwork raises questions about...",
                    "why_this_activity": "Assesses philosophical thinking and metacognition"
                },
                {
                    "id": "activity_2",
                    "type": "text",
                    "title": "Your Looking Process",
                    "prompt": "Reflect on how your understanding changed during the slow looking experience. What surprised you about your own process of seeing?",
                    "placeholder": "My understanding evolved...",
                    "why_this_activity": "Assesses metacognitive awareness"
                }
            ]
        }
        
        return stage_activities.get(stage, stage_activities[1])
