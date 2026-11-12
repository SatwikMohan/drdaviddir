"""Local, zero-cost routing with recent-subject continuity."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    category: str = "DIRECT_CONVERSATION"

    @property
    def local(self):
        return self.category in {"PERSONAL_MEMORY", "LOCAL_KNOWLEDGE", "HYBRID_KNOWLEDGE"}

    @property
    def personal(self):
        return self.category == "PERSONAL_MEMORY"


PERSONAL = re.compile(r"\b(?:your|you|penman)\b.{0,75}\b(?:thesis|publication|paper|career|background|academic interests|achievements|history|life|research|professional experience|education|journey)\b|\b(?:thesis|publication|paper|career|background|academic interests|achievements|history|life|research|professional experience|education|journey)\b.{0,75}\b(?:your|you|penman)\b", re.I)
LOCAL = re.compile(r"\b(?:uploaded|indexed|stored notes?|private knowledge|the document|the paper|my research|our research|my thesis|your thesis|your publications?|iit\s*\(?ism\)?|indian school of mines|dhanbad)\b", re.I)
CURRENT = re.compile(r"\b(?:today|yesterday|right now|this (?:morning|week|month)|currently|current (?:market )?(?:price|rate|score|news)|latest (?:\w+ ){0,2}(?:news|release|papers?|research|developments?|model)|breaking news|live (?:price|updates?))\b", re.I)
HYBRID = re.compile(r"\b(?:compare|contrast|relate|versus|vs\.?|against|how does|how do|in light of)\b", re.I)
FOLLOW_UP = re.compile(r"\b(?:it|that|those|them|this|more|earlier|previous|discussed)\b", re.I)
OPINION = re.compile(r"^(?:what do you think|how do you feel|why do you think)\b", re.I)


def route(question: str, history=None) -> Route:
    q = question.strip()
    if re.fullmatch(r"(?:how are you(?: today)?|good (?:morning|afternoon|evening)|hello|hi)[?.! ]*", q, re.I):
        return Route()
    if CURRENT.search(q):
        return Route("CURRENT_INFORMATION_UNAVAILABLE")
    personal = bool(PERSONAL.search(q)) and not bool(OPINION.search(q))
    local = bool(LOCAL.search(q)) or personal
    if history and FOLLOW_UP.search(q) and not local:
        previous = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        previous_route = route(previous)
        local, personal = previous_route.local, previous_route.personal
    if local:
        if HYBRID.search(q) and not personal:
            return Route("HYBRID_KNOWLEDGE")
        return Route("PERSONAL_MEMORY" if personal else "LOCAL_KNOWLEDGE")
    return Route()
