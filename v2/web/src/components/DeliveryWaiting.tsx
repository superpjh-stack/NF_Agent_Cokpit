import {useEffect,useState} from 'react';
import {Volume2,VolumeX} from 'lucide-react';
import {deliverySoundEnabled,rememberDeliverySound,primeDeliveryAudio,startDeliveryAudio,stopDeliveryAudio} from './deliveryAudio';
import {CargoMark,deliveryCargo,cargoLabels} from './deliveryTheme';
import './DeliveryWaiting.css';

/** A small waiting indicator, not a measure of request progress. */
export default function DeliveryWaiting({active,audible=true,question=''}:{active:boolean;audible?:boolean;question?:string}){
 const cargo=deliveryCargo(question);
 const [visible,setVisible]=useState(active);
 const [sound,setSound]=useState(deliverySoundEnabled);
 useEffect(()=>{
  const sync=()=>{if(active&&audible&&sound&&!document.hidden)startDeliveryAudio();else stopDeliveryAudio()};
  sync();document.addEventListener('visibilitychange',sync);
  return()=>{document.removeEventListener('visibilitychange',sync);stopDeliveryAudio()};
 },[active,audible,sound]);
 useEffect(()=>{
  if(active){setVisible(true);return}
  const timer=setTimeout(()=>setVisible(false),480);
  return()=>clearTimeout(timer);
 },[active]);
 if(!visible)return null;
 return <div className={"delivery-waiting"+(active?"":" is-leaving")} role={active?"status":undefined} aria-hidden={!active||undefined} aria-label="답변을 준비하고 있습니다. 자료와 근거를 확인 중입니다.">
  <span className="delivery-scene" aria-hidden="true">
   <span className="delivery-vehicle" data-cargo={cargo}><span className="delivery-trail"/>
   <svg className="delivery-rider" viewBox="0 0 48 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <ellipse cx="25" cy="37" rx="19" ry="1.3" fill="#315543" opacity=".12"/>
    <g className="delivery-wheel wheel-back"><circle cx="12" cy="31" r="5.5" fill="#34483e"/><circle cx="12" cy="31" r="2.5" fill="#cddbcf"/><path d="M12 29v4m-2-2h4" stroke="#7d9686" strokeWidth="1"/></g>
    <g className="delivery-wheel wheel-front"><circle cx="38" cy="31" r="5.5" fill="#34483e"/><circle cx="38" cy="31" r="2.5" fill="#cddbcf"/><path d="M38 29v4m-2-2h4" stroke="#7d9686" strokeWidth="1"/></g>
    <path d="M8 25h13l5 5h8l-2-11h5l5 9h-8l-4 6H16l-4-6H8z" fill="#367456"/>
    <path d="M32 19h4l-2-5h-4" stroke="#34483e" strokeWidth="2" strokeLinecap="round"/>
    <path d="M10 24h12" stroke="#273e31" strokeWidth="3" strokeLinecap="round"/>
    <CargoMark kind={cargo}/>
    <path d="m25 12-6 9 8 2-1 7h5l1-10-7-3 4-4" fill="#284f3b"/>
    <path d="m26 13 4 5h5" stroke="#5c9570" strokeWidth="3" strokeLinecap="round"/>
    <circle cx="28" cy="8" r="4.5" fill="#e9c9a3"/>
    <path d="M23 8a5 5 0 0 1 10 0h-6v3h-3z" fill="#426f52"/>
    <path d="M28 7h5" stroke="#c8ded0" strokeWidth="1.6" strokeLinecap="round"/>
    <path d="M40 23h2" stroke="#efce83" strokeWidth="2" strokeLinecap="round"/>
   </svg></span>
  </span>
  <span className="delivery-caption">답변 배달 중<span className="delivery-dots" aria-hidden="true"><i/><i/><i/></span><button type="button" className="delivery-sound" disabled={!active} aria-label={sound?'바이크 소리 끄기':'바이크 소리 켜기'} aria-pressed={sound} title={sound?'바이크 소리 끄기':'바이크 소리 켜기'} onClick={()=>{const next=!sound;rememberDeliverySound(next);if(next)primeDeliveryAudio();else stopDeliveryAudio();setSound(next)}}>{sound?<Volume2 size={13}/>:<VolumeX size={13}/>}</button></span>
 </div>;
}
