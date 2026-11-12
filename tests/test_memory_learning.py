from unittest.mock import patch
import config
from services import memory
from services.intent_router import route
from services.language_service import detect_language


def test_explicit_memory_persists_and_correction_replaces(tmp_path):
    with patch.object(config, "MEMORY_DB_FILE", str(tmp_path / "memory.sqlite3")):
        assert memory.save("I prefer detailed explanations with practical examples.", "turn-1")
        assert "detailed explanations" in memory.relevant("Explain this")
        assert memory.save("I prefer concise explanations.", "turn-2")
        assert "concise explanations" in memory.relevant("Explain this")
        assert "detailed explanations" not in memory.relevant("Explain this")
        assert not memory.save("Hello there.")
        assert not memory.save("Imagine I am researching lunar geology.")
        assert len(list(tmp_path.glob("*.sqlite3"))) == 1


def test_routes_and_language():
    cases = [
        ("Hello", "DIRECT_CONVERSATION"), ("Explain quantum computing", "DIRECT_CONVERSATION"),
        ("What do you think about education?", "DIRECT_CONVERSATION"),
        ("What did your thesis cover?", "PERSONAL_MEMORY"),
        ("Tell me about your career", "PERSONAL_MEMORY"),
        ("What is in my uploaded document?", "LOCAL_KNOWLEDGE"),
        ("Summarise my indexed paper", "LOCAL_KNOWLEDGE"),
        ("Compare my research with educational theory", "HYBRID_KNOWLEDGE"),
        ("What happened in AI today?", "CURRENT_INFORMATION_UNAVAILABLE"),
        ("What is the current market price?", "CURRENT_INFORMATION_UNAVAILABLE"),
    ]
    for question, expected in cases:
        assert route(question).category == expected, question
    assert detect_language("What is quantum computing at IIT Dhanbad?") == "en"
    assert detect_language("Mujhe batao kya hai") != "en"
    assert detect_language("कृपया बताइए") != "en"


def test_routing_paraphrases():
    groups = {
        "DIRECT_CONVERSATION": ["Good morning", "How are you today?", "What is coal?", "Explain gravity", "Why is education important?", "Can we discuss ethics?", "Tell me about mathematics", "What do you think about art?", "How does a turbine work?", "What is a hypothesis?"],
        "PERSONAL_MEMORY": ["Describe your background", "What was your career?", "Tell me about your thesis", "What were your academic interests?", "Explain your research", "What was your education?", "Describe your achievements", "Tell me about your life", "What is your professional experience?", "How did your journey begin?"],
        "LOCAL_KNOWLEDGE": ["Summarise the uploaded document", "What does the indexed paper say?", "Explain my research", "Read the stored notes", "What is in the document?", "What does my thesis say?", "Describe the uploaded file", "Find the indexed material", "What is in the paper?", "Summarise the private knowledge"],
        "CURRENT_INFORMATION_UNAVAILABLE": ["What happened today?", "What was announced yesterday?", "What is the current price?", "Give me breaking news", "What is happening right now?", "What is the latest model?", "What are the latest research papers?", "What is the current market price?", "What are the latest AI developments?", "Give me live updates"],
    }
    for category, questions in groups.items():
        for question in questions:
            assert route(question).category == category, question
