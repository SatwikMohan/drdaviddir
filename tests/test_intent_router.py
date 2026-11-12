from services.intent_router import route


def test_routes_without_model_calls():
    assert route("How are you?") == route("What do you think about education?")
    assert not route("What is coal?").local
    assert route("Tell me about your academic journey").local
    assert route("What did your thesis cover?").personal
    assert route("What is in the uploaded paper?").local
    assert route("What are the latest AI developments?").category == "CURRENT_INFORMATION_UNAVAILABLE"
    combined = route("How does your research compare with the latest developments?")
    assert combined.category == "CURRENT_INFORMATION_UNAVAILABLE"
    assert not route("Who are you?").local


def test_follow_up_inherits_local_topic():
    history = [{"role": "user", "content": "Tell me about your thesis"},
               {"role": "assistant", "content": "I worked on mine ventilation."}]
    assert route("Can you explain more about it?", history).local
