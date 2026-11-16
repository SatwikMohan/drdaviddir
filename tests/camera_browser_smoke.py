"""Real browser smoke test for the camera toggle and local WebSocket path."""
import sys
import base64
import io
import wave
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel="msedge", headless=True,
        args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
              "--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"])
    context = browser.new_context(viewport={"width": 1280, "height": 800}, permissions=["camera"])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
    page.wait_for_function("window.interaction && interaction.socket.readyState === WebSocket.OPEN")
    if "--proactive" in sys.argv:
        page.evaluate("""() => { const canvas=document.createElement('canvas'); canvas.width=320;canvas.height=240;
            const ctx=canvas.getContext('2d');ctx.fillStyle='#246';ctx.fillRect(0,0,320,240);
            window.syntheticCamera=canvas.captureStream(1);
            navigator.mediaDevices.getUserMedia=async()=>window.syntheticCamera }""")
    if "--missing-device" in sys.argv:
        page.evaluate("""() => { navigator.mediaDevices.getUserMedia = async () => {
            throw new DOMException('Requested device not found', 'NotFoundError') } }""")
        page.locator("#camera").click()
        assert "No webcam found" in page.locator("#cameraStatus").inner_text()
        assert page.locator("#camera").inner_text() == "Camera off"
        browser.close()
        print("PASS: missing webcam gives an actionable message")
        raise SystemExit(0)
    page.evaluate("""() => { interaction.sentTypes=[]; const send=interaction.send.bind(interaction);
        interaction.send=(message)=>{interaction.sentTypes.push(message.type);send(message)} }""")
    page.locator("#camera").click()
    page.wait_for_function("interaction.sentTypes.includes('camera_frame')", timeout=10000)
    print("BUTTON", page.locator("#camera").inner_text())
    print("STATUS", page.locator("#cameraStatus").inner_text())
    print("TRACK", page.evaluate("interaction.cameraStream?.getVideoTracks()[0]?.readyState || null"))
    print("ERRORS", errors)
    assert page.locator("#camera").inner_text() == "Camera on"
    assert page.evaluate("interaction.cameraStream.getVideoTracks()[0].readyState") == "live"
    assert page.evaluate("interaction.sentTypes.includes('camera_start')")
    if "--proactive" in sys.argv:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(16000)
            sound.writeframes(b"\0\0" * 32000)
        payload = base64.b64encode(buffer.getvalue()).decode()
        page.evaluate("encoded => interaction.event({type:'proactive_audio',audio:encoded,mime:'audio/wav'})", payload)
        page.wait_for_function("interaction.proactivePlaying && interaction.state === 'speaking'")
        page.wait_for_function("!interaction.proactivePlaying && interaction.state === 'idle'", timeout=10000)
        assert page.evaluate("interaction.lastReportedState === 'idle'")
    if "--wait-for-vision" in sys.argv:
        page.wait_for_function("document.getElementById('cameraStatus').textContent === 'Visual context ready'", timeout=150000)
        print("VISION", page.locator("#cameraStatus").inner_text())
    page.locator("#camera").click()
    assert page.evaluate("interaction.cameraStream === null")
    assert page.evaluate("interaction.sentTypes.includes('camera_stop')")
    browser.close()
