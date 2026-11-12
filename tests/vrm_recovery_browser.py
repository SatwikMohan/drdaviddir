"""Offline visual checks for the recovered VRM; no API calls."""
import io
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frontend"))
from avatar_renderer import import_map, model_uri
import config

SCRIPT = r'''
import * as THREE from 'three';
import {GLTFLoader} from 'three/GLTFLoader.js';
import {applyAPose,disableInvalidMorphTargets} from 'avatar/pose';
const gltf=await new GLTFLoader().loadAsync(__MODEL__);
const root=gltf.scene, invalid=disableInvalidMorphTargets(root);
const pose=applyAPose(root,45);
const scene=new THREE.Scene();scene.add(root);
scene.add(new THREE.HemisphereLight(0xffffff,0x555555,2));
const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(1,2,3);scene.add(light);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(400,400);renderer.setClearColor(0x303030);
document.body.appendChild(renderer.domElement);
const camera=new THREE.PerspectiveCamera(30,1,.01,100);
camera.position.set(0,1.445,.62);camera.lookAt(0,1.445,0);
const meshes=[];root.traverse(n=>{if(n.isMesh&&n.morphTargetInfluences?.length)meshes.push(n)});
window.report={invalid,applied:pose.applied,meshes:meshes.map(n=>({name:n.name,targets:n.morphTargetDictionary,
 vertices:n.geometry.attributes.position.count,counts:n.geometry.morphAttributes.position.map(a=>a.count)}))};
window.setShapes=(values)=>{for(const mesh of meshes){mesh.morphTargetInfluences.fill(0);
 for(const [name,value] of Object.entries(values)){const index=mesh.morphTargetDictionary[name];
 if(index!==undefined)mesh.morphTargetInfluences[index]=value;}}
 renderer.render(scene,camera);
};
window.fullBody=()=>{camera.position.set(0,.8,3.5);camera.lookAt(0,.8,0)};
renderer.setAnimationLoop(()=>renderer.render(scene,camera));window.ready=true;
'''

with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True,args=["--enable-unsafe-swiftshader"])
    page=browser.new_page(viewport={"width":400,"height":400})
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
    page.set_content('<html><head><script type="importmap">'+import_map()+'</script></head>'+
                     '<body style="margin:0"><script type="module">'+
                     SCRIPT.replace('__MODEL__',json.dumps(model_uri(config.AVATAR_MODEL_FILE)))+'</script></body></html>')
    page.wait_for_function('window.ready',timeout=60000)
    report=page.evaluate('report')
    assert not report['invalid'] and report['applied']
    assert len(report['meshes'])==1
    assert report['meshes'][0]['counts']==[28456]*11
    names=list(report['meshes'][0]['targets'])
    assert names==['aa','ih','ee','oh','ou','blinkLeft','blinkRight','blink','happy','angry','surprised']
    folder=ROOT/'docs'/'vrm-recovery';folder.mkdir(exist_ok=True)
    for group,targets in [('mouth',names[:5]),('expressions',names[5:])]:
        sheet=Image.new('RGB',(1000,len(targets)*220),(30,30,30));draw=ImageDraw.Draw(sheet)
        for row,name in enumerate(targets):
            for col,value in enumerate([0,.25,.5,.75,1]):
                page.evaluate('setShapes', {name:value})
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                picture=Image.open(io.BytesIO(page.screenshot())).resize((200,200))
                sheet.paste(picture,(col*200,row*220));draw.text((col*200+3,row*220+202),f'{name} {value}',fill='white')
        sheet.save(folder/f'{group}.jpg')
    page.evaluate('setShapes',{})
    page.screenshot(path=str(folder/'neutral.png'))
    page.evaluate('fullBody()')
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    page.screenshot(path=str(folder/'a-pose.png'))
    assert not errors,errors
    report['errors']=errors;report['levels_tested']=[0,.25,.5,.75,1]
    (folder/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n')
    browser.close()
print('PASS: 11 named targets, matched counts, A-pose, all target levels rendered without WebGL errors')
