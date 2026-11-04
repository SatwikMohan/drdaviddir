"""Real Edge/WebGL acceptance with a mocked remote voice service."""
import base64
import io
import json
import math
from pathlib import Path
import struct
import wave
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/"tests"/"artifacts"
ARTIFACTS.mkdir(exist_ok=True)
buf=io.BytesIO()
with wave.open(buf,"wb") as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
    w.writeframes(b"".join(struct.pack("<h",int(1500*math.sin(i*2*math.pi*200/16000))) for i in range(32000)))
encoded=base64.b64encode(buf.getvalue()).decode()
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True,args=["--use-fake-ui-for-media-stream","--use-fake-device-for-media-stream","--enable-unsafe-swiftshader","--autoplay-policy=no-user-gesture-required"])
    page=browser.new_page(viewport={"width":1280,"height":900})
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.add_init_script("""window.sent=[];
    class FakeSocket {
      static OPEN=1;
      constructor(){this.readyState=0;setTimeout(()=>{this.readyState=1;this.onopen?.()},50)}
      send(raw){const m=JSON.parse(raw);window.sent.push(m);
        if(m.type==='utterance'){this.rid=m.request_id;setTimeout(()=>this.onmessage?.({data:JSON.stringify({type:'audio',request_id:m.request_id,sequence:0,mime:'audio/wav',audio:ENCODED})}),100)}
        if(m.type==='played')this.onmessage?.({data:JSON.stringify({type:'done',request_id:m.request_id})});
      }
      close(){this.readyState=3}
    }
    window.WebSocket=FakeSocket;
    """.replace("ENCODED",json.dumps(encoded)))
    page.goto("http://127.0.0.1:8000",wait_until="networkidle")
    page.wait_for_selector("#modelStatus.loaded",state="attached",timeout=30000)
    assert page.locator("button").count()==1
    assert page.locator("input,textarea").count()==0
    assert page.title()=="Dr. David Panman"
    page.screenshot(path=str(ARTIFACTS/"desktop.png"))
    page.click("#microphone")
    page.wait_for_function("window.interaction.recording")
    page.evaluate("async()=>{const m=window.interaction;await m.context.suspend();for(let i=0;i<40;i++)m.samples(new Float32Array(1024).fill(.1));m.lastSpeech=performance.now()-2000;m.samples(new Float32Array(1024))}")
    page.wait_for_function("window.interaction.state==='speaking'")
    assert page.evaluate("sent.filter(x=>x.type==='utterance').length")==1
    old=page.evaluate("interaction.id")
    # Natural barge-in through the same energy detector, no extra button.
    page.evaluate("()=>{for(let i=0;i<40;i++)interaction.samples(new Float32Array(1024).fill(.1))}")
    page.wait_for_function("interaction.recording")
    assert page.evaluate("document.getElementById('audio').paused")
    assert page.evaluate("interaction.id")!=old
    page.evaluate("rid=>interaction.event({type:'audio',request_id:rid,sequence:1,audio:'',mime:'audio/wav'})",old)
    assert page.evaluate("interaction.queue.length")==0
    page.evaluate("()=>{interaction.lastSpeech=performance.now()-2000;interaction.samples(new Float32Array(1024))}")
    page.wait_for_function("interaction.state==='idle'",timeout=10000)
    assert page.evaluate("sent.filter(x=>x.type==='utterance').length")==2
    page.set_viewport_size({"width":390,"height":844})
    page.wait_for_timeout(700)
    page.screenshot(path=str(ARTIFACTS/"mobile.png"))
    assert not errors,errors
    browser.close()
print("PASS: WebGL, responsive layout, one microphone, VAD submission, ordered audio, natural interruption, stale-event rejection, idle recovery")
