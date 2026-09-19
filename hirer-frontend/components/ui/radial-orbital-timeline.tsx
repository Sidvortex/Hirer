"use client";
import {useState,useEffect,useRef} from "react";
import {ArrowRight,Zap} from "lucide-react";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";
import {Card,CardContent,CardHeader,CardTitle} from "@/components/ui/card";
interface TimelineItem{id:number;title:string;date:string;content:string;category:string;icon:React.ElementType;relatedIds:number[];status:"completed"|"in-progress"|"pending";energy:number;}
interface Props{timelineData:TimelineItem[];onSelect?:(id:number)=>void;}
export default function RadialOrbitalTimeline({timelineData,onSelect}:Props){
  const[expanded,setExpanded]=useState<Record<number,boolean>>({});
  const[rotation,setRotation]=useState(0);
  const[autoRotate,setAutoRotate]=useState(true);
  const[pulse,setPulse]=useState<Record<number,boolean>>({});
  const[activeId,setActiveId]=useState<number|null>(null);
  const[radius,setRadius]=useState(160);
  const containerRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{let t:ReturnType<typeof setInterval>;if(autoRotate){t=setInterval(()=>setRotation(r=>Number(((r+0.25)%360).toFixed(3))),50);}return()=>{if(t)clearInterval(t);};},[autoRotate]);
  useEffect(()=>{const update=()=>{if(containerRef.current){const w=containerRef.current.offsetWidth,h=containerRef.current.offsetHeight;setRadius(Math.min(w,h)*0.36);}};update();window.addEventListener("resize",update);return()=>window.removeEventListener("resize",update);},[]);
  const toggle=(id:number)=>{setExpanded(prev=>{const n:Record<number,boolean>={};Object.keys(prev).forEach(k=>{n[parseInt(k)]=false;});n[id]=!prev[id];if(!prev[id]){setActiveId(id);setAutoRotate(false);const p:Record<number,boolean>={};(timelineData.find(i=>i.id===id)?.relatedIds||[]).forEach(r=>{p[r]=true;});setPulse(p);}else{setActiveId(null);setAutoRotate(true);setPulse({});}return n;});if(onSelect)onSelect(id);};
  const pos=(index:number,total:number)=>{const angle=((index/total)*360+rotation)%360,rad=(angle*Math.PI)/180,x=radius*Math.cos(rad),y=radius*Math.sin(rad);return{x,y,zIndex:Math.round(100+50*Math.cos(rad)),opacity:Math.max(0.5,Math.min(1,0.5+0.5*((1+Math.sin(rad))/2)))};};
  const statusStyle=(s:TimelineItem["status"])=>s==="completed"?"text-white bg-black border-white":s==="in-progress"?"text-black bg-white border-black":"text-white bg-black/40 border-white/50";
  return(
    <div className="w-full h-full flex items-center justify-center bg-black overflow-hidden" ref={containerRef} onClick={e=>{if(e.target===containerRef.current){setExpanded({});setActiveId(null);setPulse({});setAutoRotate(true);}}}>
      <div className="relative flex items-center justify-center" style={{width:radius*2+120,height:radius*2+120}}>
        <div className="absolute w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 via-blue-500 to-teal-500 flex items-center justify-center z-10 pointer-events-none"><div className="absolute w-20 h-20 rounded-full border border-white/20 animate-ping opacity-50"/><div className="w-7 h-7 rounded-full bg-white/80"/></div>
        <div className="absolute rounded-full border border-white/10 pointer-events-none" style={{width:radius*2,height:radius*2}}/>
        {timelineData.map((item,index)=>{const p=pos(index,timelineData.length),isExp=expanded[item.id],isRel=activeId?(timelineData.find(i=>i.id===activeId)?.relatedIds||[]).includes(item.id):false,Icon=item.icon;
          return(<div key={item.id} className="absolute transition-all duration-500 cursor-pointer" style={{transform:`translate(${p.x}px,${p.y}px)`,zIndex:isExp?200:p.zIndex,opacity:isExp?1:p.opacity}} onClick={e=>{e.stopPropagation();toggle(item.id);}}>
            <div className={`absolute rounded-full pointer-events-none ${pulse[item.id]?"animate-pulse":""}`} style={{background:"radial-gradient(circle,rgba(255,255,255,0.15) 0%,transparent 70%)",width:`${item.energy*0.4+36}px`,height:`${item.energy*0.4+36}px`,left:`-${(item.energy*0.4+36-40)/2}px`,top:`-${(item.energy*0.4+36-40)/2}px`}}/>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${isExp?"bg-white text-black scale-150 border-white shadow-lg shadow-white/30":isRel?"bg-white/50 text-black border-white animate-pulse":"bg-black text-white border-white/50"}`}><Icon size={16}/></div>
            <div className={`absolute top-12 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] font-semibold tracking-wider text-center transition-all duration-300 ${isExp?"text-white":"text-white/80"}`}>{item.title}</div>
            {isExp&&(<Card className="absolute top-20 left-1/2 -translate-x-1/2 w-60 bg-black/95 backdrop-blur-lg border-white/20 shadow-xl z-50">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-px h-3 bg-white/30"/>
              <CardHeader className="pb-2 pt-4 px-4"><div className="flex justify-between items-center"><Badge className={`px-2 text-[10px] ${statusStyle(item.status)}`}>{item.status==="completed"?"DONE":item.status==="in-progress"?"ACTIVE":"PENDING"}</Badge><span className="text-[10px] font-mono text-white/40">{item.date}</span></div><CardTitle className="text-sm mt-2 text-white">{item.title}</CardTitle></CardHeader>
              <CardContent className="text-[11px] text-white/70 px-4 pb-4"><p>{item.content}</p>
                <div className="mt-3 pt-3 border-t border-white/10"><div className="flex justify-between items-center text-[10px] mb-1"><span className="flex items-center text-white/50 gap-1"><Zap size={9}/>Match</span><span className="font-mono text-white">{item.energy}%</span></div><div className="w-full h-0.5 bg-white/10 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-blue-500 to-purple-500" style={{width:`${item.energy}%`}}/></div></div>
                {item.relatedIds.length>0&&<div className="mt-3 pt-3 border-t border-white/10"><div className="flex flex-wrap gap-1">{item.relatedIds.map(rid=>{const r=timelineData.find(i=>i.id===rid);return(<Button key={rid} variant="outline" size="sm" className="h-5 px-2 text-[10px] rounded-none border-white/20 bg-transparent hover:bg-white/10 text-white/60 hover:text-white" onClick={e=>{e.stopPropagation();toggle(rid);}}>{r?.title}<ArrowRight size={7} className="ml-1"/></Button>);})}</div></div>}
              </CardContent>
            </Card>)}
          </div>);
        })}
      </div>
    </div>
  );
}
