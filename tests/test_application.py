from fastapi.testclient import TestClient
from unittest.mock import patch
import config
from main import app
from avatar_renderer import avatar_asset_manifest

def test_page_and_public_configuration():
    with TestClient(app) as client:
        response=client.get("/")
        assert response.status_code==200
        html=response.text
        assert html.count("<button")==2 and 'id="camera"' in html and "<input" not in html and "<textarea" not in html
        assert "Khoj" not in html
        assert "AI-generated voice" in html
        with patch.object(config,"OPENAI_API_KEY","secret-marker"):
            assert "secret-marker" not in client.get("/config").text
        assert client.get("/health").status_code==200
        assert client.get("/static/interaction.js").status_code==200

def test_missing_credentials_readiness():
    with patch.object(config,"OPENAI_API_KEY",""),TestClient(app) as client:
        assert client.get("/ready").status_code==503

def test_assets_exact_case_and_rig():
    from tools.inspect_facial_asset import inspect
    path, model, resources=avatar_asset_manifest(config.AVATAR_MODEL_FILE)
    inventory = inspect(path)
    assert inventory["skins"] and not inventory["animations"]
    assert not inventory["validation_errors"]
    assert "aa" in inventory["meshes"][0]["target_names"]


def test_websocket_end_to_end_with_mocked_provider():
    import base64
    from unittest.mock import AsyncMock
    async def answer(*args):
        yield "The indexed manual describes a bucket wheel excavator with rotating buckets."
    with patch("services.conversation.api.transcribe",AsyncMock(return_value="What does your indexed paper say about a bucket wheel excavator?")) as stt,patch("services.conversation.retrieve",return_value="A bucket wheel excavator has rotating buckets.") as retrieval,patch("services.conversation.api.generate",side_effect=answer) as generation,patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")) as tts,TestClient(app) as client:
        with client.websocket_connect("/voice",headers={"origin":"http://testserver"}) as ws:
            payload={"type":"utterance","request_id":"websocket-0001","audio":base64.b64encode(b"audio").decode(),"mime":"audio/wav"}
            ws.send_json(payload)
            states=[]
            while True:
                event=ws.receive_json()
                assert event["request_id"]==payload["request_id"]
                if event["type"]=="state": states.append(event["state"])
                if event["type"]=="audio": ws.send_json({"type":"played","request_id":payload["request_id"],"sequence":event["sequence"]})
                if event["type"]=="done": break
                assert event["type"]!="error"
            assert states==["transcribing","retrieving","generating"]
            ws.send_json(payload)
            assert ws.receive_json()["type"]=="duplicate"
            assert stt.call_count==retrieval.call_count==generation.call_count==tts.call_count==1


def test_visual_question_uses_cached_scene_even_with_right_now():
    import base64
    from unittest.mock import AsyncMock
    async def answer(*args):
        yield "I can see a red book."
    scene = {"scene_summary": "A red book is held up to the camera", "objects": ["book"],
             "visible_text": [], "confidence": .8, "timestamp": "2026-11-14T00:00:00Z", "status": "available"}
    with patch("services.vision.VisualPerception.context", return_value=scene), \
         patch("services.conversation.api.transcribe", AsyncMock(return_value="What can you see right now?")), \
         patch("services.conversation.api.generate", side_effect=answer) as generation, \
         patch("services.conversation.api.synthesize", AsyncMock(return_value=b"RIFF")), \
         TestClient(app) as client:
        with client.websocket_connect("/voice", headers={"origin": "http://testserver"}) as ws:
            request_id = "visual-question-0001"
            ws.send_json({"type": "utterance", "request_id": request_id,
                          "audio": base64.b64encode(b"audio").decode(), "mime": "audio/wav"})
            while True:
                event = ws.receive_json()
                if event["type"] == "audio":
                    ws.send_json({"type": "played", "request_id": request_id, "sequence": event["sequence"]})
                if event["type"] == "done":
                    break
                assert event["type"] != "error"
    assert generation.call_count == 1
    assert "A red book is held up to the camera" in generation.call_args.args[1]
