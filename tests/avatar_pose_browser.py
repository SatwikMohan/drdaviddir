"""Offline Edge/WebGL pose check; no OpenAI or microphone requests.

Run: .venv/Scripts/python.exe tests/avatar_pose_browser.py
"""
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frontend"))
from avatar_renderer import import_map, model_uri
import config

SCRIPT = r'''
import * as THREE from 'three';
import {GLTFLoader} from 'three/GLTFLoader.js';
import {applyAPose, disableInvalidMorphTargets} from 'avatar/pose';
const gltf = await new GLTFLoader().loadAsync(__MODEL__);
const root = gltf.scene;
const rejected = disableInvalidMorphTargets(root);
const mesh = root.getObjectByName('output_unwrapped');
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(900,1000);renderer.setClearColor(0x303030);
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();scene.add(root);
scene.add(new THREE.HemisphereLight(0xffffff,0x315442,3.2));
const key = new THREE.DirectionalLight(0xffffff,2.8);key.position.set(2,3,4);scene.add(key);
root.updateMatrixWorld(true);
const box = new THREE.Box3().setFromObject(root), center = box.getCenter(new THREE.Vector3());
const camera = new THREE.PerspectiveCamera(35,.9,.01,100);
camera.position.set(center.x,center.y,center.z+3.4);camera.lookAt(center);
const captureBones = () => Object.fromEntries(['LeftArm','LeftForeArm','LeftHand','RightArm','RightForeArm','RightHand']
  .map(name => [name,root.getObjectByName(name).getWorldPosition(new THREE.Vector3()).toArray()]));
const original = captureBones();
window.poseCheck = {rejected, original, disabledCount:mesh.morphTargetInfluences.length};
window.showA = () => {
  window.pose = applyAPose(root,45);
  poseCheck.applied = window.pose.applied;poseCheck.posed = captureBones();renderer.render(scene,camera);
};
window.restoreT = () => {window.pose.restore();poseCheck.restored=captureBones();renderer.render(scene,camera)};
window.showFace = () => {
  camera.position.set(center.x,box.max.y-.2,center.z+1.05);
  camera.lookAt(center.x,box.max.y-.2,center.z);renderer.render(scene,camera);
};
renderer.setAnimationLoop(() => renderer.render(scene,camera));window.poseReady=true;
'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True, args=["--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 900, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    script = SCRIPT.replace("__MODEL__", json.dumps(model_uri(config.AVATAR_MODEL_FILE)))
    page.set_content('<html><head><script type="importmap">'+import_map()+
                     '</script></head><body style="margin:0"><script type="module">'+script+'</script></body></html>')
    page.wait_for_function("window.poseReady", timeout=60000)
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    page.screenshot(path=str(ROOT / "docs/avatar-t-pose.png"))
    page.evaluate("showA()")
    page.screenshot(path=str(ROOT / "docs/avatar-a-pose.png"))
    page.evaluate("restoreT()")
    page.screenshot(path=str(ROOT / "docs/avatar-t-pose.png"))
    result = page.evaluate("poseCheck")
    assert result["applied"]
    assert result["rejected"] == [] and result["disabledCount"] == 11
    for side in ("Left", "Right"):
        arm, elbow, hand = [result["posed"][side + part] for part in ("Arm", "ForeArm", "Hand")]
        assert hand[1] < elbow[1] < arm[1], (side, arm, elbow, hand)
        dx, dy = abs(elbow[0] - arm[0]), abs(elbow[1] - arm[1])
        assert abs(dx - dy) < 1e-5, "Upper arm must slope at 45 degrees"
    for name, position in result["original"].items():
        assert max(abs(a-b) for a,b in zip(position,result["restored"][name])) < 1e-6
    page.evaluate("showA();showFace()")
    page.screenshot(path=str(ROOT / "docs/avatar-latest-face.png"))
    assert not errors, errors
    (ROOT / "docs/avatar-pose-validation.json").write_text(json.dumps(result, indent=2)+"\n")
    browser.close()
print("PASS: recovered GLB loaded; valid targets preserved; A-pose arm directions; T-pose restoration; no WebGL/page errors")
