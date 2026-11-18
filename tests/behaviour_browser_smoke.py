"""Run against a local backend to check conversational browser states."""
import base64
import io
import wave

from playwright.sync_api import sync_playwright


buffer = io.BytesIO()
with wave.open(buffer, "wb") as sound:
    sound.setnchannels(1)
    sound.setsampwidth(2)
    sound.setframerate(16000)
    sound.writeframes(b"\0\0" * 4000)
sample = base64.b64encode(buffer.getvalue()).decode()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True,
        args=["--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
    page.wait_for_function("window.interaction && interaction.socket.readyState === WebSocket.OPEN")
    page.evaluate("""() => {
        interaction.id='behaviour-smoke';interaction.nextSequence=0;interaction.done=false;
        interaction.event({type:'state',request_id:'behaviour-smoke',state:'transcribing'});
    }""")
    assert "Listening back" in page.locator("#status").inner_text()
    assert page.locator("#visual").get_attribute("data-state") == "processing"
    page.evaluate("""() => interaction.event({type:'behaviour',request_id:'behaviour-smoke',
        text:'Let me think that through.',delivery:'thoughtful',purpose:'acknowledgement'})""")
    assert page.locator("#status").inner_text() == "Let me think that through."
    page.evaluate("""() => interaction.event({type:'state',request_id:'behaviour-smoke',state:'retrieving'})""")
    assert "Checking the relevant details" in page.locator("#status").inner_text()
    page.evaluate("""() => interaction.event({type:'state',request_id:'behaviour-smoke',state:'synthesizing'})""")
    assert "Preparing my spoken reply" in page.locator("#status").inner_text()
    page.evaluate("""() => { window.playedSequences=[];
        document.getElementById('audio').addEventListener('playing',
            () => window.playedSequences.push(interaction.currentAudio?.sequence));
        interaction.sentAt=performance.now(); }""")
    page.evaluate("""sample => {
        interaction.event({type:'audio',request_id:'behaviour-smoke',sequence:0,
            audio:sample,mime:'audio/wav',purpose:'acknowledgement',delivery:'warm'});
        interaction.event({type:'audio',request_id:'behaviour-smoke',sequence:1,
            audio:sample,mime:'audio/wav',purpose:'answer',delivery:'neutral'});
        interaction.event({type:'done',request_id:'behaviour-smoke'});
    }""", sample)
    page.wait_for_function("interaction.state === 'idle' && interaction.done", timeout=10000)
    played = page.evaluate("window.playedSequences")
    assert played == [0, 1], played
    assert not errors, errors
    browser.close()
    print("PASS: processing states, cue text and ordered audio playback")
