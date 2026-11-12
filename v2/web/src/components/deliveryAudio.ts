/** Quiet synthesized scooter engine; no downloads or microphone permissions. */
let context:AudioContext|null=null;
let current:{gain:GainNode;sources:OscillatorNode[];nodes:AudioNode[]}|null=null;
export function deliverySoundEnabled(){try{return localStorage.getItem('needsfood_delivery_sound')!=='off'}catch{return true}}
export function rememberDeliverySound(enabled:boolean){try{localStorage.setItem('needsfood_delivery_sound',enabled?'on':'off')}catch{/* optional preference */}}
export function primeDeliveryAudio(){
 if(!deliverySoundEnabled())return;
 try{context??=new AudioContext();if(context.state==='suspended')void context.resume().catch(()=>{})}catch{/* Audio is optional. */}
}
export function startDeliveryAudio(){
 if(current||!deliverySoundEnabled())return;
 primeDeliveryAudio();if(!context||context.state==='closed')return;
 const ctx=context,now=ctx.currentTime;
 const master=ctx.createGain();master.gain.setValueAtTime(0,now);master.gain.linearRampToValueAtTime(.045,now+.65);master.connect(ctx.destination);
 const filter=ctx.createBiquadFilter();filter.type='lowpass';filter.frequency.value=420;filter.Q.value=.55;filter.connect(master);
 const pulseGain=ctx.createGain();pulseGain.gain.value=.5;pulseGain.connect(filter);
 const engine=ctx.createOscillator();engine.type='sawtooth';engine.frequency.value=62;engine.connect(pulseGain);
 const harmonic=ctx.createOscillator();harmonic.type='triangle';harmonic.frequency.value=124;const harmonicGain=ctx.createGain();harmonicGain.gain.value=.22;harmonic.connect(harmonicGain);harmonicGain.connect(filter);
 const pulse=ctx.createOscillator();pulse.frequency.value=18;const pulseDepth=ctx.createGain();pulseDepth.gain.value=.22;pulse.connect(pulseDepth);pulseDepth.connect(pulseGain.gain);
 const rev=ctx.createOscillator();rev.frequency.value=.22;const revDepth=ctx.createGain();revDepth.gain.value=5;rev.connect(revDepth);revDepth.connect(engine.frequency);
 const sources=[engine,harmonic,pulse,rev];sources.forEach(source=>source.start());
 current={gain:master,sources,nodes:[master,filter,pulseGain,harmonicGain,pulseDepth,revDepth]};
}
export function stopDeliveryAudio(){
 if(!current||!context)return;
 const voice=current;current=null;const now=context.currentTime;
 voice.gain.gain.cancelScheduledValues(now);voice.gain.gain.setTargetAtTime(0,now,.1);
 voice.sources.forEach(source=>{try{source.stop(now+.42)}catch{/* already stopped */}});
 setTimeout(()=>{voice.sources.forEach(source=>source.disconnect());voice.nodes.forEach(node=>node.disconnect())},470);
}
