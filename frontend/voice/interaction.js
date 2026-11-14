const stage=document.getElementById("visual"), button=document.getElementById("microphone"), status=document.getElementById("status"), audio=document.getElementById("audio");
export function wavBuffer(chunks,rate){
 const length=chunks.reduce((n,c)=>n+c.length,0), bytes=new ArrayBuffer(44+length*2), view=new DataView(bytes);
 const word=(offset,s)=>{for(let i=0;i<s.length;i++)view.setUint8(offset+i,s.charCodeAt(i))};
 word(0,"RIFF");view.setUint32(4,36+length*2,true);word(8,"WAVE");word(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,"data");view.setUint32(40,length*2,true);
 let at=44;for(const chunk of chunks)for(const value of chunk){view.setInt16(at,Math.max(-1,Math.min(1,value))*32767,true);at+=2}return bytes;
}
export class InteractionManager{
 constructor(cfg){this.cfg=cfg;this.id=null;this.userId=localStorage.getItem("penmanUserId")||crypto.randomUUID();localStorage.setItem("penmanUserId",this.userId);this.queue=[];this.state="idle";this.epoch=0;this.recording=false;this.playing=false;this.recoverable=false;this.preRoll=[];this.barge=0;this.frames=[];this.connect()}
 setState(state,message){this.state=state;stage.dataset.state=state;status.textContent=message||({idle:"Tap the microphone to begin",listening:"I'm listening... Pause when you have finished.",processing:"Just a moment...",transcribing:"Just a moment...",retrieving:"Just a moment...",generating:"Just a moment...",speaking:"You may speak to interrupt",interrupted:"I'm listening...",error:"Please try again"}[state]||"");button.setAttribute("aria-label",this.recoverable?"Retry remaining speech":state==="speaking"?"Interrupt and speak":"Start speaking");button.disabled=state==="listening"}
 connect(){this.socket=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/voice`);this.socket.onopen=()=>{button.disabled=false;this.setState("idle");if(this.cameraStream)this.send({type:"camera_start"})};this.socket.onmessage=e=>this.event(JSON.parse(e.data));this.socket.onclose=()=>this.fail("The connection closed. Tap the microphone to reconnect.");this.socket.onerror=()=>this.fail("Cannot connect to the conversation service.")}
 send(message){if(this.socket.readyState!==WebSocket.OPEN)throw Error("Connection unavailable");this.socket.send(JSON.stringify(message))}
 async prepare(){
  if(this.context)return;
  if(!navigator.mediaDevices?.getUserMedia)throw Error("Microphone access needs HTTPS or localhost.");
  this.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
  this.context=new AudioContext();await this.context.resume();
  this.source=this.context.createMediaStreamSource(this.stream);this.processor=this.context.createScriptProcessor(this.cfg.bufferFrames,1,1);
  this.processor.onaudioprocess=e=>this.samples(new Float32Array(e.inputBuffer.getChannelData(0)));
  const mute=this.context.createGain();mute.gain.value=0;this.source.connect(this.processor);this.processor.connect(mute);mute.connect(this.context.destination);
  this.stream.getAudioTracks()[0].onended=()=>this.fail("Microphone access ended. Reload to reconnect your microphone.");
 }
 async click(){
  if(this.starting||this.recording)return;
  this.starting=true;
  try{
   if(this.socket.readyState!==WebSocket.OPEN){this.connect();return}
   if(this.recoverable){this.nextSequence=0;this.recoverable=false;this.setState("generating");this.send({type:"recover",request_id:this.id});this.watchdog();return}
   await window.prepareAvatarAudio?.();await this.prepare();await this.context.resume();this.begin();
  }catch(error){this.fail(error.name==="NotAllowedError"?"Please allow microphone access in your browser.":error.message)}finally{this.starting=false}
 }
 stopAudio(){audio.pause();audio.removeAttribute("src");audio.load();if(this.url)URL.revokeObjectURL(this.url);this.url=null;this.queue=[];this.playing=false;this.currentAudio=null}
 begin(){
  const interrupted=this.state==="speaking";this.epoch++;this.send({type:"cancel",request_id:this.id});this.stopAudio();clearTimeout(this.timer);
  this.id=crypto.randomUUID();this.nextSequence=0;this.recoverable=false;this.done=false;this.recording=true;this.frames=[...this.preRoll];this.preRoll=[];this.started=performance.now();this.speechMs=0;this.lastSpeech=this.started;this.barge=0;
  if(interrupted)this.setState("interrupted");this.setState("listening");
  this.recordTimer=setTimeout(()=>this.submit(),this.cfg.maxRecordingMs);
 }
 samples(frame){
  const ms=frame.length/this.context.sampleRate*1000, rms=Math.sqrt(frame.reduce((n,v)=>n+v*v,0)/frame.length), now=performance.now();
  if(this.recording){this.frames.push(frame);if(rms>this.cfg.rmsThreshold){this.speechMs+=ms;this.lastSpeech=now}
   if(this.speechMs>=this.cfg.minSpeechMs&&now-this.lastSpeech>=this.cfg.silenceMs)this.submit();
  }else{
   this.preRoll.push(frame);while(this.preRoll.length>Math.ceil(this.context.sampleRate*this.cfg.preRollMs/1000/frame.length))this.preRoll.shift();
   if(["speaking","processing"].includes(this.state)){this.barge=rms>this.cfg.bargeThreshold?this.barge+ms:0;if(this.barge>=this.cfg.bargeMs){this.begin();this.speechMs=this.cfg.bargeMs}}
   else this.barge=0;
  }
 }
 async submit(){
  if(!this.recording)return;this.recording=false;clearTimeout(this.recordTimer);
  if(this.speechMs<this.cfg.minSpeechMs){this.frames=[];this.setState("idle","I didn't catch any speech. Tap to try again.");return}
  const epoch=this.epoch, captureMs=Math.round(performance.now()-this.started), blob=new Blob([wavBuffer(this.frames,this.context.sampleRate)],{type:"audio/wav"});this.frames=[];this.setState("processing");this.watchdog();
  try{const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=reject;reader.readAsDataURL(blob)});if(epoch!==this.epoch)return;this.sentAt=performance.now();this.send({type:"utterance",request_id:this.id,user_id:this.userId,capture_ms:captureMs,audio:encoded,mime:"audio/wav"})}catch{this.fail("Your recording could not be sent. Please try again.")}
 }
 watchdog(){clearTimeout(this.timer);this.timer=setTimeout(()=>{try{this.send({type:"cancel",request_id:this.id})}catch{}this.fail("The conversation timed out. Please try again.")},this.cfg.turnTimeoutMs+5000)}
 event(message){
  if(message.type==="camera_status"){
   if(this.cameraStream)document.getElementById("cameraStatus").textContent=message.ready?"Visual context ready":({analysing:"Analysing scene...",unavailable:"Vision retrying...",starting:"Waiting for visual analysis...",available:"Refreshing scene..."}[message.status]||"Waiting for camera...");
   return;
  }
  if(message.request_id!==this.id)return;
  if(message.type==="state"){if(!this.playing)this.setState(["transcribing","retrieving","generating"].includes(message.state)?"processing":message.state)}
  else if(message.type==="audio"){
   if(message.sequence!==this.nextSequence||this.queue.length>=this.cfg.queueLimit){this.fail("Audio arrived out of order. Please try again.");return}
   this.nextSequence++;this.queue.push(message);this.playNext();
  }else if(message.type==="done"){this.done=true;this.finish()}
  else if(message.type==="error"){this.recoverable=!!message.recoverable;this.fail(message.message,this.recoverable)}
 }
 async playNext(){
  if(this.playing||!this.queue.length)return;this.playing=true;
  const segment=this.queue.shift(), epoch=this.epoch;this.currentAudio=segment;
  try{
   const bytes=Uint8Array.from(atob(segment.audio),c=>c.charCodeAt(0));this.url=URL.createObjectURL(new Blob([bytes],{type:segment.mime}));audio.src=this.url;
   audio.onended=()=>{if(epoch!==this.epoch)return;this.send({type:"played",request_id:this.id,sequence:segment.sequence});URL.revokeObjectURL(this.url);this.url=null;this.playing=false;this.currentAudio=null;this.playNext();this.finish()};
   audio.onerror=()=>{if(epoch===this.epoch)this.fail("Audio playback failed. Tap the microphone to speak again.")};
   await audio.play();if(epoch===this.epoch){if(segment.sequence===0)this.send({type:"audible",request_id:this.id,latency_ms:Math.round(performance.now()-this.sentAt)});this.setState("speaking")}
  }catch{if(epoch===this.epoch)this.fail("Audio playback is blocked. Tap the microphone and try again.")}
 }
 finish(){if(this.done&&!this.playing&&!this.queue.length){clearTimeout(this.timer);this.setState("idle")}}
 fail(message,preserve=false){this.epoch++;clearTimeout(this.timer);clearTimeout(this.recordTimer);this.recording=false;this.frames=[];this.stopAudio();if(!preserve){this.recoverable=false;try{this.send({type:"cancel",request_id:this.id})}catch{}}this.setState("error",message);button.disabled=false}
 dispose(){this.epoch++;clearTimeout(this.timer);clearTimeout(this.recordTimer);this.stopCamera();this.stopAudio();this.stream?.getTracks().forEach(t=>t.stop());this.context?.close();this.socket.close()}
}
InteractionManager.prototype.toggleCamera=async function(){
 if(this.cameraStream){this.stopCamera();return}
 const label=document.getElementById("cameraStatus");
 label.textContent="Starting camera...";
 try{
  if(!navigator.mediaDevices?.getUserMedia)throw Error("Camera access needs HTTPS or localhost.");
  const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:this.cfg.cameraWidth},height:{ideal:this.cfg.cameraWidth},frameRate:{ideal:1}},audio:false});
  this.cameraStream=stream;this.cameraVideo=document.createElement("video");this.cameraVideo.srcObject=stream;this.cameraVideo.muted=true;this.cameraVideo.playsInline=true;this.cameraVideo.autoplay=true;
  this.cameraVideo.style.cssText="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none";document.body.appendChild(this.cameraVideo);
  await this.cameraVideo.play();
  stream.getVideoTracks()[0].onended=()=>this.stopCamera();this.send({type:"camera_start"});
  document.getElementById("camera").textContent="Camera on";document.getElementById("camera").setAttribute("aria-label","Disable camera");label.textContent="Waiting for visual analysis...";
  this.cameraTimer=setInterval(()=>this.captureFrame(),this.cfg.cameraIntervalMs);this.captureFrame();
 }catch(error){this.stopCamera();label.textContent=error.name==="NotAllowedError"?"Camera permission denied":error.message}
};
InteractionManager.prototype.captureFrame=function(){
 if(!this.cameraStream||this.socket.readyState!==WebSocket.OPEN||this.socket.bufferedAmount>250000||!this.cameraVideo.videoWidth)return;
 const canvas=document.createElement("canvas"),ratio=Math.min(1,this.cfg.cameraWidth/this.cameraVideo.videoWidth);canvas.width=Math.round(this.cameraVideo.videoWidth*ratio);canvas.height=Math.round(this.cameraVideo.videoHeight*ratio);
 canvas.getContext("2d").drawImage(this.cameraVideo,0,0,canvas.width,canvas.height);
 const image=canvas.toDataURL("image/jpeg",.65).split(",")[1];if(image.length<330000)this.send({type:"camera_frame",image});
};
InteractionManager.prototype.stopCamera=function(){clearInterval(this.cameraTimer);this.cameraTimer=null;this.cameraStream?.getTracks().forEach(t=>t.stop());this.cameraStream=null;if(this.cameraVideo){this.cameraVideo.srcObject=null;this.cameraVideo.remove()}this.cameraVideo=null;try{this.send({type:"camera_stop"})}catch{}document.getElementById("camera").textContent="Camera off";document.getElementById("camera").setAttribute("aria-label","Enable camera");document.getElementById("cameraStatus").textContent="Camera off"};
try{const response=await fetch("/config");if(!response.ok)throw Error("Configuration unavailable");const cfg=await response.json();document.title=cfg.name;document.getElementById("name").textContent=cfg.name;const manager=new InteractionManager(cfg);window.interaction=manager;button.addEventListener("click",()=>manager.click());document.getElementById("camera").addEventListener("click",()=>manager.toggleCamera());window.addEventListener("pagehide",()=>manager.dispose())}catch{status.textContent="The application could not connect. Please reload."}
