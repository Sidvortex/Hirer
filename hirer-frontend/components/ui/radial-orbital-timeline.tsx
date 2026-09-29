"use client";
import { useState, useEffect, useRef } from "react";
import { ArrowRight, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TimelineItem {
  id: number;
  title: string;
  date: string;
  content: string;
  category: string;
  icon: React.ElementType;
  relatedIds: number[];
  status: "completed" | "in-progress" | "pending";
  energy: number;
}

interface RadialOrbitalTimelineProps {
  timelineData: TimelineItem[];
  onSelect?: (id: number) => void;
}

export default function RadialOrbitalTimeline({
  timelineData,
  onSelect,
}: RadialOrbitalTimelineProps) {
  const [expandedItems, setExpandedItems] = useState<Record<number, boolean>>({});
  const [rotationAngle, setRotationAngle] = useState<number>(0);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [pulseEffect, setPulseEffect] = useState<Record<number, boolean>>({});
  const [activeNodeId, setActiveNodeId] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const orbitRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const handleContainerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === containerRef.current || e.target === orbitRef.current) {
      setExpandedItems({});
      setActiveNodeId(null);
      setPulseEffect({});
      setAutoRotate(true);
    }
  };

  const toggleItem = (id: number) => {
    setExpandedItems((prev) => {
      const newState: Record<number, boolean> = {};
      Object.keys(prev).forEach((key) => { newState[parseInt(key)] = false; });
      newState[id] = !prev[id];
      if (!prev[id]) {
        setActiveNodeId(id);
        setAutoRotate(false);
        const relatedItems = getRelatedItems(id);
        const newPulse: Record<number, boolean> = {};
        relatedItems.forEach((relId) => { newPulse[relId] = true; });
        setPulseEffect(newPulse);
      } else {
        setActiveNodeId(null);
        setAutoRotate(true);
        setPulseEffect({});
      }
      return newState;
    });
  };

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    if (autoRotate) {
      timer = setInterval(() => {
        setRotationAngle((prev) => Number(((prev + 0.25) % 360).toFixed(3)));
      }, 50);
    }
    return () => { if (timer) clearInterval(timer); };
  }, [autoRotate]);

  // radius scales with container — use 38% of the shorter dimension
  const [radius, setRadius] = useState(160);
  useEffect(() => {
    const update = () => {
      if (containerRef.current) {
        const w = containerRef.current.offsetWidth;
        const h = containerRef.current.offsetHeight;
        // keep nodes within bounds — radius = 40% of half the shorter side
        setRadius(Math.min(w, h) * 0.36);
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const calculateNodePosition = (index: number, total: number) => {
    const angle = ((index / total) * 360 + rotationAngle) % 360;
    const radian = (angle * Math.PI) / 180;
    const x = radius * Math.cos(radian);
    const y = radius * Math.sin(radian);
    const zIndex = Math.round(100 + 50 * Math.cos(radian));
    const opacity = Math.max(0.5, Math.min(1, 0.5 + 0.5 * ((1 + Math.sin(radian)) / 2)));
    return { x, y, zIndex, opacity };
  };

  const getRelatedItems = (itemId: number): number[] => {
    const current = timelineData.find((item) => item.id === itemId);
    return current ? current.relatedIds : [];
  };

  const isRelatedToActive = (itemId: number): boolean => {
    if (!activeNodeId) return false;
    return getRelatedItems(activeNodeId).includes(itemId);
  };

  const getStatusStyles = (status: TimelineItem["status"]): string => {
    switch (status) {
      case "completed": return "text-white bg-black border-white";
      case "in-progress": return "text-black bg-white border-black";
      default: return "text-white bg-black/40 border-white/50";
    }
  };

  return (
    <div
      className="w-full h-full flex flex-col items-center justify-center bg-black overflow-hidden"
      ref={containerRef}
      onClick={handleContainerClick}
    >
      <div
        className="relative flex items-center justify-center"
        ref={orbitRef}
        style={{ width: radius * 2 + 120, height: radius * 2 + 120 }}
      >
        {/* Center pulsing node */}
        <div className="absolute w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 via-blue-500 to-teal-500 flex items-center justify-center z-10 pointer-events-none">
          <div className="absolute w-20 h-20 rounded-full border border-white/20 animate-ping opacity-50" />
          <div className="w-7 h-7 rounded-full bg-white/80 backdrop-blur-md" />
        </div>

        {/* Orbit ring */}
        <div
          className="absolute rounded-full border border-white/10 pointer-events-none"
          style={{ width: radius * 2, height: radius * 2 }}
        />

        {/* Nodes */}
        {timelineData.map((item, index) => {
          const position = calculateNodePosition(index, timelineData.length);
          const isExpanded = expandedItems[item.id];
          const isRelated = isRelatedToActive(item.id);
          const isPulsing = pulseEffect[item.id];
          const Icon = item.icon;

          return (
            <div
              key={item.id}
              ref={(el) => { nodeRefs.current[item.id] = el; }}
              className="absolute transition-all duration-500 cursor-pointer"
              style={{
                transform: `translate(${position.x}px, ${position.y}px)`,
                zIndex: isExpanded ? 200 : position.zIndex,
                opacity: isExpanded ? 1 : position.opacity,
              }}
              onClick={(e) => {
                e.stopPropagation();
                toggleItem(item.id);
                if (onSelect) onSelect(item.id);
              }}
            >
              {/* Energy glow */}
              <div
                className={`absolute rounded-full pointer-events-none ${isPulsing ? "animate-pulse" : ""}`}
                style={{
                  background: `radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%)`,
                  width: `${item.energy * 0.4 + 36}px`,
                  height: `${item.energy * 0.4 + 36}px`,
                  left: `-${(item.energy * 0.4 + 36 - 40) / 2}px`,
                  top: `-${(item.energy * 0.4 + 36 - 40) / 2}px`,
                }}
              />

              {/* Node icon button */}
              <div
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center
                  ${isExpanded ? "bg-white text-black scale-150" : isRelated ? "bg-white/50 text-black animate-pulse" : "bg-black text-white"}
                  border-2
                  ${isExpanded ? "border-white shadow-lg shadow-white/30" : isRelated ? "border-white" : "border-white/50"}
                  transition-all duration-300
                `}
              >
                <Icon size={16} />
              </div>

              {/* Label — always visible */}
              <div
                className={`
                  absolute top-12 left-1/2 -translate-x-1/2 whitespace-nowrap
                  text-[10px] font-semibold tracking-wider text-center
                  transition-all duration-300
                  ${isExpanded ? "text-white" : "text-white/80"}
                `}
              >
                {item.title}
              </div>

              {/* Expanded card */}
              {isExpanded && (
                <Card className="absolute top-20 left-1/2 -translate-x-1/2 w-60 bg-black/95 backdrop-blur-lg border-white/20 shadow-xl z-50">
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-px h-3 bg-white/30" />
                  <CardHeader className="pb-2 pt-4 px-4">
                    <div className="flex justify-between items-center">
                      <Badge className={`px-2 text-[10px] ${getStatusStyles(item.status)}`}>
                        {item.status === "completed" ? "DONE" : item.status === "in-progress" ? "ACTIVE" : "PENDING"}
                      </Badge>
                      <span className="text-[10px] font-mono text-white/40">{item.date}</span>
                    </div>
                    <CardTitle className="text-sm mt-2 text-white">{item.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-[11px] text-white/70 px-4 pb-4">
                    <p>{item.content}</p>
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <div className="flex justify-between items-center text-[10px] mb-1">
                        <span className="flex items-center text-white/50 gap-1">
                          <Zap size={9} /> Match Energy
                        </span>
                        <span className="font-mono text-white">{item.energy}%</span>
                      </div>
                      <div className="w-full h-0.5 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500" style={{ width: `${item.energy}%` }} />
                      </div>
                    </div>
                    {item.relatedIds.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-white/10">
                        <div className="flex flex-wrap gap-1">
                          {item.relatedIds.map((relatedId) => {
                            const related = timelineData.find((i) => i.id === relatedId);
                            return (
                              <Button
                                key={relatedId}
                                variant="outline"
                                size="sm"
                                className="h-5 px-2 text-[10px] rounded-none border-white/20 bg-transparent hover:bg-white/10 text-white/60 hover:text-white"
                                onClick={(e) => { e.stopPropagation(); toggleItem(relatedId); }}
                              >
                                {related?.title} <ArrowRight size={7} className="ml-1" />
                              </Button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
