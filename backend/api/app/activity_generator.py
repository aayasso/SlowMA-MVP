"""
SlowMA Activity Generator
AI-powered generation of personalized reflection activities using Anthropic Claude.
Supports all 10 activity types mapped to appropriate Housen stages.
"""

import os
import json
from typing import List, Optional
from anthropic import Anthropic
from app.models.schemas import ReflectionActivity, ActivityType
from app.cost_logger import tracked_completion


# ============================================================
# Stage + Activity Type Configuration
# ============================================================

STAGE_INFO = {
    1: {
        "name": "Accountive",
        "description": "Concrete, personal, emotional. Users tell stories and make associations.",
        "focus": "Personal reactions, colors, shapes, immediate feelings",
        "preferred_types": [
            ActivityType.LISTING,
            ActivityType.WORD_CLOUD,
            ActivityType.VOICE,
            ActivityType.TEXT,
            ActivityType.FILL_BLANK,
        ],
    },
    2: {
        "name": "Constructive",
        "description": "Building own interpretations. Creating narratives and personal meaning.",
        "focus": "Stories, personal connections, constructing meaning from observations",
        "preferred_types": [
            ActivityType.TEXT,
            ActivityType.FILL_BLANK,
            ActivityType.SORTING,
            ActivityType.VOICE,
            ActivityType.MULTIPLE_CHOICE,
        ],
    },
    3: {
        "name": "Classifying",
        "description": "Analytical, using art historical knowledge. Categorizing and comparing.",
        "focus": "Style, technique, art historical context, comparisons between works",
        "preferred_types": [
            ActivityType.CLASSIFYING,
            ActivityType.MULTIPLE_CHOICE,
            ActivityType.SORTING,
            ActivityType.TEXT,
            ActivityType.CHAT,
        ],
    },
    4: {
        "name": "Interpretive",
        "description": "Balancing personal response with formal analysis. Multiple perspectives.",
        "focus": "Synthesis of feeling and thinking, symbolic meaning, multiple interpretations",
        "preferred_types": [
            ActivityType.TEXT,
            ActivityType.CHAT,
            ActivityType.SKETCH,
            ActivityType.VOICE,
            ActivityType.CLASSIFYING,
        ],
    },
    5: {
        "name": "Re-creative",
        "description": "Deep engagement, re-experiencing the artist's creative process.",
        "focus": "Empathy with artist, understanding creative choices, universal questions",
        "preferred_types": [
            ActivityType.SKETCH,
            ActivityType.CHAT,
            ActivityType.TEXT,
            ActivityType.VOICE,
            ActivityType.SORTING,
        ],
    },
}

SUBSTAGE_INFO = {
    1: "Early — just entering this stage, needs gentle scaffolding",
    2: "Developing — building confidence at this stage",
    3: "Advanced — ready to be stretched toward the next stage",
}

ACTIVITY_TYPE_DESCRIPTIONS = {
    ActivityType.TEXT: "Open-ended written reflection. User types a free response.",
    ActivityType.MULTIPLE_CHOICE: "User selects from 4 options you generate. Good for guided interpretation.",
    ActivityType.FILL_BLANK: "A sentence with a blank for the user to complete. E.g. 'This artwork makes me feel ___ because ___'",
    ActivityType.WORD_CLOUD: "Present 8-12 words. User thumbs up/down each one based on whether it fits the artwork.",
    ActivityType.SORTING: "Present 4-6 items. User drags them into order (e.g. most to least prominent, most to least emotional).",
    ActivityType.CLASSIFYING: "Present 6-8 words or phrases. User drags each into one of 2-3 labeled categories.",
    ActivityType.LISTING: "User quickly lists 3-5 things (e.g. 'List 3 things you notice'). Low pressure, fast.",
    ActivityType.SKETCH: "User draws a quick finger sketch response (e.g. 'Sketch the mood of this work in 60 seconds').",
    ActivityType.VOICE: "User speaks their response aloud. App records and transcribes. Best for personal reflection.",
    ActivityType.CHAT: "User can ask the app questions about the artwork in a guided Q&A format.",
}

MODEL = "claude-sonnet-4-20250514"


# ============================================================
# Activity Generator
# ============================================================

class ActivityGenerator:
    """
    Generates 3 personalized reflection activities per journey using Claude.
    Activities are selected and structured based on the user's Housen stage.
    """

    def __init__(self):
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
        artwork_context: Optional[dict] = None,
        user_id: Optional[str] = None,
        journey_id: Optional[str] = None,
    ) -> List[ReflectionActivity]:
        """
        Generate 3 personalized reflection activities.

        Args:
            housen_stage: User's current Housen stage (1-5)
            housen_substage: User's substage (1-3)
            at_museum: Whether user is physically at a museum
            artwork_context: Optional dict with artwork details (title, artist, style, etc.)
            user_id: For cost logging
            journey_id: For cost logging

        Returns:
            List of 3 ReflectionActivity objects
        """
        prompt = self._build_prompt(housen_stage, housen_substage, at_museum, artwork_context)

        try:
            message = tracked_completion(
                client=self.client,
                feature="activity_generation",
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                user_id=user_id,
                journey_id=journey_id,
                housen_stage=housen_stage,
            )

            raw_text = message.content[0].text
            activities = self._parse_response(raw_text, housen_stage)
            return activities

        except Exception as e:
            print(f"Error generating activities: {e}")
            return self._fallback_activities(housen_stage)

    def _build_prompt(
        self,
        housen_stage: int,
        housen_substage: int,
        at_museum: bool,
        artwork_context: Optional[dict],
    ) -> str:

        stage = STAGE_INFO[housen_stage]
        substage = SUBSTAGE_INFO[housen_substage]
        preferred = stage["preferred_types"]

        preferred_desc = "\n".join(
            f"  - {t.value.upper()}: {ACTIVITY_TYPE_DESCRIPTIONS[t]}"
            for t in preferred
        )

        artwork_desc = "an artwork the user just spent 3-5 minutes slowly observing"
        if artwork_context:
            parts = []
            if artwork_context.get("title"):
                parts.append(f"'{artwork_context['title']}'")
            if artwork_context.get("artist"):
                parts.append(f"by {artwork_context['artist']}")
            if artwork_context.get("style"):
                parts.append(f"({artwork_context['style']})")
            if parts:
                artwork_desc = " ".join(parts)

        location = "at a museum or gallery in person" if at_museum else "viewing digitally at home or school"

        prompt = f"""You are an expert art educator for SlowMA, an app teaching visual literacy through slow looking.

The user just completed a 3-5 minute slow observation walkthrough of {artwork_desc}.
They are {location}.

USER'S DEVELOPMENTAL LEVEL:
- Housen Stage: {housen_stage} — {stage['name']}
- Description: {stage['description']}
- Focus at this stage: {stage['focus']}
- Substage: {substage}

YOUR TASK:
Generate exactly 3 reflection activities. Choose from these activity types, which are most appropriate for this user's stage:

{preferred_desc}

RULES:
1. Use 3 DIFFERENT activity types from the list above
2. Activities should build on each other (easier → more reflective)
3. Match the user's developmental level — do NOT use art jargon for Stage 1-2 users
4. Keep tone warm, encouraging, never academic or intimidating
5. Each activity must feel directly connected to what the user just observed
6. For WORD_CLOUD: include exactly 10 words in the options list
7. For MULTIPLE_CHOICE: include exactly 4 options
8. For SORTING: include exactly 5 items to sort, and specify what the sort order means
9. For CLASSIFYING: include exactly 6 items and 2-3 category labels
10. For LISTING: specify exactly how many items to list (3 or 5)
11. For FILL_BLANK: write the full sentence with ___ where the blank goes

Return your response as a JSON array with exactly 3 objects. Use this exact structure:

[
  {{
    "id": "activity_1",
    "type": "word_cloud",
    "title": "Short engaging title (max 6 words)",
    "prompt": "Clear instruction to the user (1-2 sentences)",
    "placeholder": "A helpful example or starter phrase",
    "why_this_activity": "One sentence explaining what this reveals about the user's development",
    "options": ["word1", "word2", "word3", "word4", "word5", "word6", "word7", "word8", "word9", "word10"],
    "categories": null
  }},
  {{
    "id": "activity_2",
    "type": "text",
    "title": "Short engaging title",
    "prompt": "Clear instruction to the user",
    "placeholder": "I noticed that...",
    "why_this_activity": "Pedagogical purpose",
    "options": null,
    "categories": null
  }},
  {{
    "id": "activity_3",
    "type": "fill_blank",
    "title": "Short engaging title",
    "prompt": "Complete this sentence:",
    "placeholder": "This artwork makes me feel ___ because ___",
    "why_this_activity": "Pedagogical purpose",
    "options": null,
    "categories": null
  }}
]

IMPORTANT:
- Return ONLY the JSON array. No explanation, no markdown, no backticks.
- The "options" field is only used for: word_cloud, multiple_choice, sorting, classifying
- The "categories" field is only used for: classifying
- All other fields should always be present
"""
        return prompt

    def _parse_response(self, raw_text: str, housen_stage: int) -> List[ReflectionActivity]:
        """Parse Claude's JSON response into ReflectionActivity objects."""

        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        try:
            data = json.loads(clean)

            activities = []
            for item in data:
                activity = ReflectionActivity(
                    id=item["id"],
                    type=ActivityType(item["type"]),
                    title=item["title"],
                    prompt=item["prompt"],
                    placeholder=item.get("placeholder"),
                    why_this_activity=item.get("why_this_activity"),
                    options=item.get("options"),
                    categories=item.get("categories"),
                )
                activities.append(activity)

            if len(activities) == 3:
                return activities

            print(f"Warning: expected 3 activities, got {len(activities)}. Using fallback.")
            return self._fallback_activities(housen_stage)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing activity response: {e}")
            print(f"Raw response was: {raw_text[:500]}")
            return self._fallback_activities(housen_stage)

    def _fallback_activities(self, housen_stage: int) -> List[ReflectionActivity]:
        """Safe fallback activities if API call or parsing fails."""

        return [
            ReflectionActivity(
                id="activity_1",
                type=ActivityType.LISTING,
                title="What did you notice?",
                prompt="List 3 things you noticed while looking at this artwork.",
                placeholder="1. I noticed...",
                why_this_activity="Quick listing builds observational habits without pressure.",
                options=None,
                categories=None,
            ),
            ReflectionActivity(
                id="activity_2",
                type=ActivityType.WORD_CLOUD,
                title="How does it feel?",
                prompt="Tap thumbs up on any words that describe this artwork for you.",
                placeholder=None,
                why_this_activity="Word selection reveals emotional and aesthetic response.",
                options=[
                    "calm", "tense", "mysterious", "joyful", "dark",
                    "warm", "cold", "busy", "quiet", "powerful",
                ],
                categories=None,
            ),
            ReflectionActivity(
                id="activity_3",
                type=ActivityType.FILL_BLANK,
                title="Finish the thought",
                prompt="Complete this sentence about the artwork:",
                placeholder="This artwork makes me think about ___ because ___",
                why_this_activity="Sentence completion scaffolds reflection for any stage.",
                options=None,
                categories=None,
            ),
        ]


# ============================================================
# Singleton
# ============================================================

_generator = None


def get_activity_generator() -> ActivityGenerator:
    """Get or create the ActivityGenerator singleton."""
    global _generator
    if _generator is None:
        _generator = ActivityGenerator()
    return _generator