"""Cheap deterministic routing for the voice conversation."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    local: bool = False
    web: bool = False
    personal: bool = False


PERSONAL = re.compile(r"\b(?:your|you|penman)\b.*\b(?:research|thesis|publication|paper|career|background|education|academic|work|achievement|interest|history|life|lecture|journey|school|role)\b|\b(?:research|thesis|publication|paper|career|background|education|academic|work|achievement|interest|history|life|lecture|journey|school|role)\b.*\b(?:your|you|penman)\b", re.I)
CURRENT = re.compile(r"\b(?:latest|recent|currently|today|this (?:year|month|week)|nowadays|new developments?|up.to.date|breaking|202[5-9]|203\d)\b", re.I)
LOCAL = re.compile(r"\b(?:my uploaded|the uploaded|your (?:paper|publication|thesis|research)|indexed|in the (?:document|paper|lecture)|iit\s*\(?ism\)?|indian school of mines|dhanbad|our (?:paper|research|document))\b", re.I)
IDENTITY = re.compile(r"^(?:who are you|what is your name|are you (?:dr\.? )?(?:david )?penman)[?.! ]*$", re.I)


def route(question: str, history=None) -> Route:
    q = question.strip()
    if IDENTITY.fullmatch(q):
        return Route()
    if re.match(r"^(?:what do you think|how do you feel|can we discuss|why do you think)\b", q, re.I) and not CURRENT.search(q) and not LOCAL.search(q):
        return Route()
    personal = bool(PERSONAL.search(q))
    local = personal or bool(LOCAL.search(q))
    web = bool(CURRENT.search(q))
    # Pronouns in follow-ups inherit the previous user's subject, without another model call.
    if history and re.search(r"\b(?:it|that|those|them|this|more)\b", q, re.I):
        previous = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        personal = personal or bool(PERSONAL.search(previous))
        local = local or personal or bool(LOCAL.search(previous))
    return Route(local=local, web=web, personal=personal)
