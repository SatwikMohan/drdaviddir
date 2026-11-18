"""Small, deterministic conversational cues for slow voice turns."""
import re
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    text: str
    delivery: str
    purpose: str


PHRASES = {
    "personal_intro": ("Ah, I'd be glad to tell you.", "Thank you for asking about me."),
    "personal": ("Thank you for asking.", "Ah, I'd be glad to tell you."),
    "emotional": ("Thank you for telling me.", "I hear you."),
    "opinion": ("That's worth considering.", "Let me give that some thought."),
    "academic": ("That's an interesting question.", "There are a few useful angles to that."),
    "technical": ("Let me think through the technical detail.", "I'll take that step by step."),
    "followup": ("Yes, let's pick that up.", "Let me build on what we discussed."),
    "local": ("Let me check that carefully.", "I'll look at the details."),
    "visual": ("Let me take a closer look.", "I'll check what the camera shows."),
    "complex": ("Let me think that through.", "There are a couple of parts to that."),
    "general": ("Let me consider that.", "That's a good question."),
}

PROGRESS = {
    "analysing": "The camera analysis is still running; I'll describe what it finds when it is ready.",
    "retrieving": "I'm still checking the relevant material.",
    "generating": "I'm still putting the answer together.",
}

PERSONAL = re.compile(r"\b(?:yourself|your life|your background|your career|your research|your thesis|who are you|about you)\b", re.I)
PERSONAL_INTRO = re.compile(r"\b(?:tell me about yourself|introduce yourself|who are you)\b", re.I)
EMOTIONAL = re.compile(r"\b(?:I'm worried|I am worried|I'm scared|I am scared|I'm upset|I feel|grief|anxious|afraid)\b", re.I)
OPINION = re.compile(r"\b(?:what do you think|your opinion|your view|do you believe)\b", re.I)
ACADEMIC = re.compile(r"\b(?:research|theory|methodology|thesis|engineering|technical|university|academic|evidence)\b", re.I)
TECHNICAL = re.compile(r"\b(?:algorithm|machine|system|circuit|code|software|engineering|calculation|device|mechanism)\b", re.I)
FOLLOWUP = re.compile(r"^(?:and |but |what about |how about |can you expand|tell me more|why is that|how so|could you explain that)", re.I)
COMPLEX = re.compile(r"\b(?:compare|contrast|analyse|analyze|why|how does|how do|explain|difference between)\b", re.I)
SOCIAL = re.compile(r"^(?:hello|hi|hey|thanks|thank you|good (?:morning|afternoon|evening)|how are you)[!?. ]*$", re.I)


class BehaviourEngine:
    def __init__(self, window=5):
        self.recent = deque(maxlen=window)

    def classify(self, question, route_category, visual=False, has_history=False):
        if SOCIAL.fullmatch(question.strip()):
            return "social"
        if PERSONAL_INTRO.search(question):
            return "personal_intro"
        if EMOTIONAL.search(question):
            return "emotional"
        if PERSONAL.search(question):
            return "personal"
        if visual:
            return "visual"
        if route_category in {"LOCAL_KNOWLEDGE", "PERSONAL_MEMORY", "HYBRID_KNOWLEDGE"}:
            return "local"
        if route_category == "CURRENT_INFORMATION_UNAVAILABLE":
            return "unavailable"
        if OPINION.search(question):
            return "opinion"
        if has_history and FOLLOWUP.search(question):
            return "followup"
        if TECHNICAL.search(question):
            return "technical"
        if ACADEMIC.search(question):
            return "academic"
        if COMPLEX.search(question):
            return "complex"
        if len(question.split()) <= 7:
            return "simple"
        return "general"

    def acknowledgement(self, intent):
        options = PHRASES.get(intent)
        if not options:
            return None
        phrase = next((text for text in options if text not in self.recent), options[0])
        self.recent.append(phrase)
        delivery = {"personal": "warm", "personal_intro": "warm", "emotional": "empathetic",
                    "academic": "curious", "technical": "thoughtful", "complex": "thoughtful",
                    "opinion": "thoughtful"}.get(intent, "warm")
        return Cue(phrase, delivery, "acknowledgement")

    def progress(self, stage):
        text = PROGRESS.get(stage)
        if not text:
            return None
        if text in self.recent:
            return None
        self.recent.append(text)
        return Cue(text, "thoughtful", "progress")
