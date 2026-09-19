"use client";
import {motion,AnimatePresence} from "framer-motion";
import {useEffect,useState} from "react";
const FUNNY=["Convincing the hamsters to run faster...","Loading... because teleportation isn't invented yet.","Reticulating splines.","Counting to infinity... 42% complete.","Summoning ancient code spirits...","Please wait while we pretend this is taking longer for dramatic effect.","Loading your stuff. Not our stuff. We know where ours is.","Downloading more RAM...","Teaching the AI the difference between 'their' and 'there'...","The internet is thinking really hard right now.","One moment... the electrons are lining up.","Loading... definitely not stuck.","Generating excuses for the loading time...","Please hold. The ducks are not yet in a row.","Making sure everything is broken equally.","Fetching your data from the void...","Powered by caffeine and questionable decisions.","Almost there. Probably.","Loading... if this takes too long, blame physics.","Compiling bugs into features...","Please wait. We're converting coffee into code."];
function TypingMessage({text}:{text:string}){
  const[displayed,setDisplayed]=useState("");const[idx,setIdx]=useState(0);
  useEffect(()=>{setDisplayed("");setIdx(0);},[text]);
  useEffect(()=>{if(idx>=text.length)return;const t=setTimeout(()=>{setDisplayed(d=>d+text[idx]);setIdx(i=>i+1);},28);return()=>clearTimeout(t);},[idx,text]);
  return<span>{displayed}{idx<text.length&&<span className="inline-block w-0.5 h-3 bg-white/50 ml-0.5 animate-pulse"/>}</span>;
}
export default function LoadingPage({steps,pct=0}:{steps:string[];pct?:number}){
  const[funnyMsg,setFunnyMsg]=useState(FUNNY[0]);const[msgIndex,setMsgIndex]=useState(0);const[showMsg,setShowMsg]=useState(true);
  useEffect(()=>{const t=setInterval(()=>{setShowMsg(false);setTimeout(()=>{setMsgIndex(i=>{const n=(i+1)%FUNNY.length;setFunnyMsg(FUNNY[n]);return n;});setShowMsg(true);},400);},3500);return()=>clearInterval(t);},[]);
  return(
    <div className="w-full h-screen bg-black relative overflow-hidden flex items-center justify-center">
      <div className="absolute inset-0 opacity-30" style={{background:"radial-gradient(ellipse at 20% 50%, #1a1a2e 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, #16213e 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, #0f3460 0%, transparent 50%)"}}/>
      <div className="relative z-10 w-full max-w-md px-8 text-center">
        <div className="flex justify-center mb-10">
          <div className="relative w-28 h-28">
            <motion.div className="absolute inset-0 rounded-full border border-white/15" animate={{rotate:360}} transition={{duration:3,repeat:Infinity,ease:"linear"}}/>
            <motion.div className="absolute inset-3 rounded-full border border-white/10" animate={{rotate:-360}} transition={{duration:2,repeat:Infinity,ease:"linear"}}/>
            <div className="absolute inset-0 flex items-center justify-center"><span className="text-white/50 font-mono text-sm">{pct}%</span></div>
            <motion.div className="absolute top-0 left-1/2 w-2 h-2 bg-white/70 rounded-full -translate-x-1/2 -translate-y-1" animate={{rotate:360}} transition={{duration:3,repeat:Infinity,ease:"linear"}} style={{transformOrigin:"50% 56px"}}/>
          </div>
        </div>
        <div className="w-full h-px bg-white/10 mb-8 overflow-hidden"><motion.div className="h-full bg-white/50" animate={{width:`${pct}%`}} transition={{duration:0.4,ease:"easeOut"}}/></div>
        <div className="mb-6 min-h-[32px] flex items-center justify-center">
          <AnimatePresence mode="wait">{showMsg&&<motion.p key={msgIndex} initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-6}} transition={{duration:0.3}} className="font-mono text-xs text-white/60 text-center leading-relaxed"><TypingMessage text={funnyMsg}/></motion.p>}</AnimatePresence>
        </div>
        <div className="space-y-1 max-h-36 overflow-hidden">{steps.slice(-6).map((step,i,arr)=>(<motion.div key={step+i} initial={{opacity:0,x:-8}} animate={{opacity:i===arr.length-1?0.7:0.2,x:0}} transition={{duration:0.3}} className="font-mono text-[10px] text-white/40 text-left">{i===arr.length-1?"▸ ":"  "}{step}</motion.div>))}</div>
      </div>
    </div>
  );
}
