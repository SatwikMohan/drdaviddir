"""Exercise the actual renderer with local synthesized audio, without API calls."""
import base64
import io
import math
from pathlib import Path
import struct
import sys
import wave
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'frontend'))
from avatar_renderer import render_script

buffer=io.BytesIO()
with wave.open(buffer,'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
    # Quiet speech (~.013 RMS) was rejected by the old .025 RMS gate.
    wav.writeframes(b''.join(struct.pack('<h',int(600*math.sin(i*2*math.pi*200/16000))
                    if i<32000 else 0) for i in range(48000)))
uri='data:audio/wav;base64,'+base64.b64encode(buffer.getvalue()).decode()
modules,script=render_script()
# Test-only access to the loaded scene; no production debug API.
script=script.replace('root=gltf.scene;','root=gltf.scene;window.testRoot=root;')
script=script.replace('root.position.y=baseY+Math.sin(time*(state==="listening"?1.8:1.1))*.013;',
                      'root.position.y=baseY;')
html='<html><head><script type="importmap">'+modules+'</script></head><body>'+\
     '<div id="visual" data-state="speaking"><div id="avatarScene" style="width:600px;height:600px"></div>'+\
     '<div id="modelStatus"></div><audio id="audio"></audio></div>'+script+'</body></html>'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True,args=[
        '--enable-unsafe-swiftshader','--autoplay-policy=no-user-gesture-required'])
    page=browser.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(html)
    page.wait_for_selector('#modelStatus.loaded',state='attached',timeout=60000)
    page.evaluate('''() => {
      window.mesh=testRoot.getObjectByName('output_unwrapped');
      window.aa=mesh.morphTargetDictionary.aa;
      window.player=document.getElementById('audio');
    }''')
    assert page.evaluate('mesh.morphTargetInfluences.every(v=>v===0)')
    evidence=ROOT/'docs'/'mouth-visibility';evidence.mkdir(exist_ok=True)
    page.locator('#avatarScene').screenshot(path=str(evidence/'closed.png'))
    page.evaluate('async uri=>{await prepareAvatarAudio();player.src=uri;await player.play()}',uri)
    page.wait_for_function('mesh.morphTargetInfluences[aa]>.55')
    page.locator('#avatarScene').screenshot(path=str(evidence/'quiet-speech.png'))
    assert page.evaluate('mesh.morphTargetInfluences.every((v,i)=>i===aa||v===0)')
    page.wait_for_function('player.currentTime>2.8')
    assert page.evaluate('mesh.morphTargetInfluences[aa]<.01')
    page.wait_for_function('player.ended')
    assert page.evaluate('mesh.morphTargetInfluences[aa]===0')
    page.evaluate('async()=>{player.currentTime=0;await player.play()}')
    page.wait_for_function('mesh.morphTargetInfluences[aa]>.1')
    page.evaluate('player.pause()')
    page.wait_for_function('mesh.morphTargetInfluences[aa]===0')
    page.evaluate('async()=>{player.currentTime=0;await player.play()}')
    page.wait_for_function('mesh.morphTargetInfluences[aa]>.1')
    page.evaluate("player.removeAttribute('src');player.load()")
    page.wait_for_function('mesh.morphTargetInfluences[aa]===0')
    assert page.evaluate('mesh.morphTargetInfluences.every(v=>v===0)')
    assert not errors,errors
    browser.close()
print('PASS: real audio opens only aa; silence, end, pause and source removal return mouth to neutral')
