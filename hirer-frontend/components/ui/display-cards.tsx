"use client";
import {cn} from "@/lib/utils";
import {Sparkles} from "lucide-react";
interface DisplayCardProps{className?:string;icon?:React.ReactNode;title?:string;description?:string;date?:string;titleClassName?:string;}
function DisplayCard({className,icon=<Sparkles className="size-4 text-blue-300"/>,title="Featured",description="Content",date="Now",titleClassName="text-blue-500"}:DisplayCardProps){
  return(<div className={cn("relative flex h-36 w-[22rem] -skew-y-[8deg] select-none flex-col justify-between rounded-xl border-2 bg-muted/70 backdrop-blur-sm px-4 py-3 transition-all duration-700 after:absolute after:-right-1 after:top-[-5%] after:h-[110%] after:w-[20rem] after:bg-gradient-to-l after:from-background after:to-transparent after:content-[''] hover:border-white/20 hover:bg-muted [&>*]:flex [&>*]:items-center [&>*]:gap-2",className)}><div><span className="relative inline-block rounded-full bg-blue-800 p-1">{icon}</span><p className={cn("text-lg font-medium",titleClassName)}>{title}</p></div><p className="whitespace-nowrap text-lg">{description}</p><p className="text-muted-foreground text-sm">{date}</p></div>);
}
export default function DisplayCards({cards}:{cards?:DisplayCardProps[]}){
  if(!cards||cards.length===0)return null;
  const[first,second,third]=cards;
  return(<div className="grid [grid-template-areas:'stack'] place-items-center opacity-100 animate-in fade-in-0 duration-700">
    {third&&<DisplayCard {...third} className={cn("[grid-area:stack] translate-x-24 translate-y-20 before:absolute before:w-full before:h-full before:rounded-xl before:bg-background/50 before:content-[''] before:left-0 before:top-0 grayscale-[100%] hover:translate-y-10 hover:grayscale-0 hover:before:opacity-0 before:transition-opacity before:duration-700",third.className)}/>}
    {second&&<DisplayCard {...second} className={cn("[grid-area:stack] translate-x-12 translate-y-10 before:absolute before:w-full before:h-full before:rounded-xl before:bg-background/50 before:content-[''] before:left-0 before:top-0 grayscale-[100%] hover:-translate-y-1 hover:grayscale-0 hover:before:opacity-0 before:transition-opacity before:duration-700",second.className)}/>}
    {first&&<DisplayCard {...first} className={cn("[grid-area:stack] hover:-translate-y-10",first.className)}/>}
  </div>);
}
