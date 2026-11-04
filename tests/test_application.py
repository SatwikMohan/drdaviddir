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
        assert html.count("<button")==1 and "<input" not in html and "<textarea" not in html
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
    path, model, resources=avatar_asset_manifest(config.AVATAR_MODEL_FILE)
    assert resources and not model.get("animations")
    assert any("jaw" in n.get("name","").lower() for n in model["nodes"])


def test_websocket_end_to_end_with_mocked_provider():
    import base64
    from unittest.mock import AsyncMock
    async def answer(*args):
        yield "The indexed manual describes a bucket wheel excavator with rotating buckets."
    with patch("services.conversation.api.transcribe",AsyncMock(return_value="What is a bucket wheel excavator?")) as stt,patch("services.conversation.retrieve",return_value="A bucket wheel excavator has rotating buckets.") as retrieval,patch("services.conversation.api.generate",side_effect=answer) as generation,patch("services.conversation.api.synthesize",AsyncMock(return_value=b"RIFF")) as tts,TestClient(app) as client:
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
