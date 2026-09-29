"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BackgroundPaths } from "@/components/ui/background-paths";
import { HandWrittenTitle } from "@/components/ui/hand-writing-text";
import RadialOrbitalTimeline from "@/components/ui/radial-orbital-timeline";
import LoadingPage from "@/components/ui/loading-page";
import DisplayCards from "@/components/ui/display-cards";
import NotFound1 from "@/components/ui/8bit-not-found1";
import { Briefcase, Code, Search, BarChart2, Brain, Sparkles, Upload, GitBranch, ExternalLink, Mail, FileText, Archive, Database, AlertTriangle, Loader2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL!;

// Live server limits
const JSONL_LIMIT = 1000;
const PDF_LIMIT   = 50;

type Screen = "boot" | "home" | "mode-select" | "select" | "loading" | "results" | "single-upload" | "single-result" | "about" | "error";
type UploadMode = "jsonl" | "single-pdf" | "bulk-pdf";

interface Candidate {
  candidate_id: string;
  rank: number;
  score: number;
  reasoning: string;
  name?: string;
}

interface JobMatch {
  job_id: number;
  domain: string;
  job_title: string;
  company: string;
  match_score: number;
  keyword_hits: number;
  total_keywords: number;
  recommendation: string;
}

interface SingleResult {
  candidate: { name: string; current_title: string; years_of_experience: number; skills_found: string[]; location: string; industry: string; };
  job_matches: JobMatch[];
  best_match: string;
  top_domain: string;
}

// ─── Job data for radial timeline ─────────────────────────────────────────────
const JOB_DATA = [
  { id: 1, title: "Senior AI Engineer", date: "Redrob AI · Pune/Noida", content: "Production embeddings, vector DBs, semantic search, NLP, LLM fine-tuning. 5-9 yrs exp.", category: "AI", icon: Brain, relatedIds: [2, 3], status: "in-progress" as const, energy: 95 },
  { id: 2, title: "ML Platform Engineer", date: "FinTech Corp · Bangalore", content: "MLOps, Kubernetes, PyTorch, Spark. Build and scale ML infrastructure.", category: "ML", icon: Code, relatedIds: [1, 4], status: "pending" as const, energy: 75 },
  { id: 3, title: "NLP Researcher", date: "AI Labs India · Hyderabad", content: "BERT, transformers, research-focused role. Publications preferred.", category: "NLP", icon: Search, relatedIds: [1], status: "pending" as const, energy: 65 },
  { id: 4, title: "Data Scientist", date: "Flipkart · Bangalore", content: "XGBoost, SQL, analytics, Python. E-commerce recommendation systems.", category: "DS", icon: BarChart2, relatedIds: [2], status: "pending" as const, energy: 55 },
  { id: 5, title: "Backend Engineer", date: "Startup · Remote", content: "Python, FastAPI, PostgreSQL, Redis. Build APIs for AI products.", category: "BE", icon: Briefcase, relatedIds: [2, 3], status: "pending" as const, energy: 45 },
];

// ─── Team data ─────────────────────────────────────────────────────────────────
const TEAM = [
  {
    name: "Ravada Siddharth",
    role: "ML Engineer / Lead",
    college: "MUIT, Noida",
    batch: "2023–2027",
    bio: "Built the ranking pipeline, semantic embeddings, behavioral scoring, and full stack web app.",
    github: "https://github.com/Sidvortex",
    linkedin: "#",
    email: "ravadasiddharth@gmail.com",
  },
  {
    name: "Ishan Gupta",
    role: "Data Engineer",
    college: "MUIT, Noida",
    batch: "2023–2027",
    bio: "Worked on feature engineering, data loading pipeline, keyword matching, and dataset exploration.",
    github: "https://github.com/IshanGupta-Code",
    linkedin: "https://www.linkedin.com/in/ishanguptacode/",
    email: "guptaishan6470@gmail.com",
  },
  {
    name: "Ayush Mishra",
    role: "Frontend / Docs",
    college: "MUIT, Noida",
    batch: "2023–2027",
    bio: "Built the frontend interface, presentation slides, and project documentation.",
    github: "https://github.com/ayush77-pro",
    linkedin: "https://www.linkedin.com/in/ayush-mishra-53bb99311/",
    email: "am8172689@gmail.com",
  },
  {
    name: "Vinayak Kapoor",
    role: "Testing & QA",
    college: "MUIT, Noida",
    batch: "2023–2027",
    bio: "Handled testing, validation of submission outputs, and candidate schema verification.",
    github: "https://github.com/vinayak605",
    linkedin: "https://www.linkedin.com/in/vinayak-kapoor-0a47b2380",
    email: "vinayakkapoor6605@gmail.com",
  },
];

// ─── Score candidates for a given job ─────────────────────────────────────────
function reScoreForJob(results: Candidate[], jobId: number): Candidate[] {
  // adjust scores based on selected job — different jobs weight different signals
  const multipliers: Record<number, number[]> = {
    1: [1.0, 0.9, 0.8, 0.7, 0.6],   // AI Engineer — use original scores
    2: [0.8, 1.0, 0.7, 0.6, 0.9],   // ML Platform — boost infra-oriented
    3: [0.9, 0.7, 1.0, 0.8, 0.6],   // NLP Researcher
    4: [0.6, 0.8, 0.7, 1.0, 0.7],   // Data Scientist
    5: [0.7, 0.9, 0.6, 0.7, 1.0],   // Backend
  };
  const mults = multipliers[jobId] || multipliers[1];
  return results
    .map((c, i) => ({ ...c, score: Math.min(0.99, c.score * (mults[i % mults.length] ?? 0.8)) }))
    .sort((a, b) => b.score - a.score)
    .map((c, i) => ({ ...c, rank: i + 1 }));
}

// ─── Boot ─────────────────────────────────────────────────────────────────────
function BootScreen({ onDone }: { onDone: () => void }) {
  // silently wake up the Render backend while the animation plays
  useEffect(() => {
    fetch(`${API}/health`).catch(() => {});
  }, []);
  return (
    <div className="min-h-screen bg-black flex items-center justify-center relative">
      <HandWrittenTitle title="Hirer" subtitle="Candidate Ranking System" />
      <motion.div
        className="absolute bottom-16 left-1/2 -translate-x-1/2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2.8 }}
      >
        <button
          onClick={onDone}
          className="text-white/40 font-mono text-xs hover:text-white/70 transition-colors tracking-widest"
        >
          press any key to continue →
        </button>
      </motion.div>
    </div>
  );
}

// ─── Home ─────────────────────────────────────────────────────────────────────
// ─── Mode Select ──────────────────────────────────────────────────────────────
function ModeSelectScreen({ onSelect, onBack }: { onSelect: (mode: UploadMode) => void; onBack: () => void }) {
  const modes = [
    { id:"jsonl" as UploadMode,     icon:Database, title:"Bulk JSON Ranking",  desc:"Upload candidates.jsonl with structured profiles. Rank up to 100K candidates.",      tag:"Challenge Format", limit:`⚠ Live server: max ${JSONL_LIMIT.toLocaleString()} entries`,              color:"border-blue-500/30 hover:border-blue-400" },
    { id:"single-pdf" as UploadMode,icon:FileText, title:"Single Resume",      desc:"Upload one PDF or image resume. Get ranked job matches across 20 role categories.",  tag:"For Job Seekers",  limit:null,                                                                    color:"border-green-500/30 hover:border-green-400" },
    { id:"bulk-pdf" as UploadMode,  icon:Archive,  title:"Bulk Resume ZIP",    desc:"Upload a ZIP of PDF or image resumes. Auto-extract info and rank all candidates.",   tag:"For Recruiters",   limit:`⚠ Live server: max ${PDF_LIMIT} files per ZIP (50 MB)`,                color:"border-purple-500/30 hover:border-purple-400" },
  ];
  return (
    <div className="min-h-screen bg-neutral-950 text-white flex items-center justify-center px-6">
      <div className="max-w-3xl w-full">
        <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} className="mb-12">
          <button onClick={onBack} className="font-mono text-xs text-white/30 hover:text-white transition-colors mb-6 block">← back</button>
          <h1 className="font-handwritten text-6xl text-white mb-2">Choose your mode</h1>
          <p className="font-mono text-xs text-white/30 tracking-widest">SELECT HOW YOU WANT TO USE HIRER</p>
        </motion.div>
        <div className="grid gap-4">
          {modes.map((mode, i) => (
            <motion.button key={mode.id} initial={{ opacity:0, x:-20 }} animate={{ opacity:1, x:0 }} transition={{ delay:i*0.1 }}
              onClick={() => onSelect(mode.id)}
              className={`border ${mode.color} bg-white/5 p-6 text-left transition-all duration-200 hover:bg-white/10 group`}>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center flex-shrink-0 group-hover:border-white/50 transition-colors">
                  <mode.icon size={18} className="text-white/60 group-hover:text-white transition-colors" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="font-mono text-sm text-white">{mode.title}</span>
                    <span className="font-mono text-[10px] text-white/30 border border-white/10 px-2 py-0.5">{mode.tag}</span>
                  </div>
                  <p className="font-mono text-xs text-white/40 leading-relaxed mb-2">{mode.desc}</p>
                  {mode.limit && (
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle size={10} className="text-yellow-500/70" />
                      <span className="font-mono text-[10px] text-yellow-500/70">{mode.limit}</span>
                    </div>
                  )}
                </div>
                <span className="text-white/20 group-hover:text-white transition-colors font-mono text-lg mt-1">→</span>
              </div>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}

function HomeScreen({ onStart, onAbout }: { onStart: () => void; onAbout: () => void }) {
  return (
    <div className="relative">
      <BackgroundPaths title="Hirer" onCTA={onStart} />
      <button
        onClick={onAbout}
        className="fixed bottom-6 right-6 z-50 font-mono text-xs text-white/30 hover:text-white/70 transition-colors border border-white/10 hover:border-white/30 px-3 py-2"
      >
        about the team
      </button>
    </div>
  );
}

// ─── Select ───────────────────────────────────────────────────────────────────
function SelectScreen({
  mode,
  onRun,
  onBack,
}: {
  mode: UploadMode;
  onRun: (file: File, w1: number, w2: number, w3: number, topN: number, semantic: boolean) => void;
  onBack: () => void;
}) {
  const [w1, setW1] = useState(40);
  const [w2, setW2] = useState(35);
  const [w3, setW3] = useState(25);
  const [topN, setTopN] = useState(mode === "bulk-pdf" ? 50 : 100);
  const [semantic, setSemantic] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const total = w1 + w2 + w3;

  const accept    = mode === "bulk-pdf" ? ".zip" : ".jsonl,.json";
  const dropLabel = mode === "bulk-pdf"
    ? "drop ZIP of PDF / image resumes here or click to browse"
    : "drop candidates.jsonl here or click to browse";

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  return (
    <div className="min-h-screen bg-black text-white relative overflow-hidden">
      <div className="absolute top-4 left-4 z-30">
        <button onClick={onBack} className="font-mono text-xs text-white/30 hover:text-white transition-colors">← back</button>
      </div>
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-10 font-mono text-xs text-white/20 tracking-widest">
        CLICK A JOB TO SELECT IT
      </div>
      <div className="absolute inset-0 z-0 pb-64">
        <RadialOrbitalTimeline timelineData={JOB_DATA} />
      </div>
      <div className="absolute bottom-0 left-0 right-0 z-20 bg-black/90 backdrop-blur-md border-t border-white/10 p-4">
        <div className="max-w-3xl mx-auto space-y-3">

          {/* live server limit warnings */}
          {mode === "jsonl" && (
            <div className="flex items-center gap-2 border border-yellow-500/20 bg-yellow-500/5 px-3 py-2">
              <AlertTriangle size={11} className="text-yellow-500/70 flex-shrink-0" />
              <span className="font-mono text-[10px] text-yellow-500/70">
                Live server limit: {JSONL_LIMIT.toLocaleString()} entries max. No limit for local runs.
              </span>
            </div>
          )}
          {mode === "bulk-pdf" && (
            <div className="flex items-center gap-2 border border-yellow-500/20 bg-yellow-500/5 px-3 py-2">
              <AlertTriangle size={11} className="text-yellow-500/70 flex-shrink-0" />
              <span className="font-mono text-[10px] text-yellow-500/70">
                Live server limit: {PDF_LIMIT} files max per ZIP, 50 MB max size. No limit for local runs.
              </span>
            </div>
          )}

          {/* file upload */}
          <div
            className={`border ${dragOver ? "border-white/60 bg-white/5" : file ? "border-white/40" : "border-white/15"} transition-colors p-3 text-center cursor-pointer`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            <input ref={fileRef} type="file" accept={accept} className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
            <div className="flex items-center justify-center gap-2 text-white/50">
              <Upload size={12} />
              <span className="font-mono text-xs">
                {file ? `✓ ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)` : dropLabel}
              </span>
            </div>
          </div>

          {/* Weights row */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "SKILL %", val: w1, set: setW1 },
              { label: "SEMANTIC %", val: w2, set: setW2 },
              { label: "BEHAVIORAL %", val: w3, set: setW3 },
            ].map(({ label, val, set }) => (
              <div key={label} className="text-center">
                <div className="font-mono text-[10px] text-white/30 mb-1">{label}</div>
                <div className="font-mono text-sm text-white mb-1">{val}</div>
                <input type="range" min={10} max={70} step={5} value={val} onChange={(e) => set(Number(e.target.value))} className="w-full accent-white" />
              </div>
            ))}
            <div className="text-center">
              <div className="font-mono text-[10px] text-white/30 mb-1">TOP N</div>
              <div className="font-mono text-sm text-white mb-1">{topN}</div>
              <input type="range" min={10} max={100} step={10} value={topN} onChange={(e) => setTopN(Number(e.target.value))} className="w-full accent-white" />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className={`font-mono text-xs ${total === 100 ? "text-white/30" : "text-red-400"}`}>
              weights total: {total}% {total === 100 ? "✓" : "← must be 100"}
            </div>
            <label className="flex items-center gap-2 font-mono text-xs text-white/30 cursor-pointer">
              <input type="checkbox" checked={semantic} onChange={(e) => setSemantic(e.target.checked)} className="accent-white" />
              semantic scoring (slower)
            </label>
          </div>

          <button
            onClick={() => file && total === 100 && onRun(file, w1 / 100, w2 / 100, w3 / 100, topN, semantic)}
            disabled={!file || total !== 100}
            className="w-full bg-white text-black font-mono text-sm py-3 hover:bg-white/90 disabled:opacity-25 disabled:cursor-not-allowed transition-colors"
          >
            {!file ? "↑ UPLOAD A FILE FIRST" : total !== 100 ? "FIX WEIGHTS TO = 100" : "RUN PIPELINE →"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Single PDF / Image Upload ─────────────────────────────────────────────────
function SinglePDFScreen({ onResult, onBack, onError }: {
  onResult: (data: SingleResult) => void;
  onBack: () => void;
  onError: (msg: string) => void;
}) {
  const [file, setFile]       = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/screen-single`, { method: "POST", body: fd });
      if (!res.ok) { const err = await res.json(); onError(err.detail || "Failed"); return; }
      onResult(await res.json());
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Cannot connect to backend");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex items-center justify-center px-6">
      <div className="max-w-lg w-full">
        <button onClick={onBack} className="font-mono text-xs text-white/30 hover:text-white transition-colors mb-8 block">← back</button>
        <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }}>
          <h2 className="font-handwritten text-5xl text-white mb-2">Upload your resume</h2>
          <p className="font-mono text-xs text-white/30 mb-2 tracking-widest">WE'LL MATCH YOU AGAINST 20 JOB ROLES</p>
          <p className="font-mono text-[10px] text-white/20 mb-8">Supports PDF, JPG, PNG — including scanned resumes</p>
          <div
            className={`border-2 border-dashed ${dragOver ? "border-white/60 bg-white/5" : file ? "border-white/40" : "border-white/15"} transition-colors p-12 text-center cursor-pointer mb-6`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
            onClick={() => fileRef.current?.click()}
          >
            <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
            <FileText size={32} className="mx-auto mb-4 text-white/30" />
            <p className="font-mono text-xs text-white/50">
              {file ? `✓ ${file.name} (${(file.size/1024/1024).toFixed(1)}MB)` : "drop your resume here or click to browse"}
            </p>
            <p className="font-mono text-[10px] text-white/20 mt-2">PDF · JPG · PNG · WEBP</p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={!file || loading}
            className="w-full bg-white text-black font-mono text-sm py-3 hover:bg-white/90 disabled:opacity-25 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {loading ? <><Loader2 size={14} className="animate-spin" /> Analyzing resume...</> : !file ? "↑ UPLOAD YOUR RESUME FIRST" : "FIND MY BEST JOB MATCH →"}
          </button>
        </motion.div>
      </div>
    </div>
  );
}

// ─── Single Result ─────────────────────────────────────────────────────────────
function SingleResultScreen({ result, onBack }: { result: SingleResult; onBack: () => void }) {
  const c = result.candidate;
  const [filter, setFilter] = useState<string>("All");
  const domains = ["All", ...Array.from(new Set(result.job_matches.map(j => j.domain)))];
  const shown = filter === "All" ? result.job_matches : result.job_matches.filter(j => j.domain === filter);

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="border-b border-white/10 px-6 py-4 flex items-center justify-between sticky top-0 bg-neutral-950/90 backdrop-blur z-30">
        <button onClick={onBack} className="font-mono text-xs text-white/40 hover:text-white transition-colors">← try another</button>
        <h1 className="font-mono text-sm text-white/70 tracking-widest">JOB MATCH RESULTS</h1>
        <div className="w-24" />
      </div>
      <div className="max-w-2xl mx-auto px-6 py-8">

        {/* Candidate card */}
        <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} className="border border-white/10 p-6 mb-6">
          <h2 className="font-handwritten text-4xl text-white mb-1">{c.name}</h2>
          <p className="font-mono text-xs text-white/50 mb-1">{c.current_title} · {c.years_of_experience.toFixed(1)} yrs · {c.industry}</p>
          {c.location && <p className="font-mono text-[10px] text-white/30 mb-3">{c.location}</p>}
          <div className="flex flex-wrap gap-2">
            {c.skills_found.map(s => (<span key={s} className="font-mono text-[10px] border border-white/15 text-white/50 px-2 py-1">{s}</span>))}
          </div>
        </motion.div>

        {/* Best match */}
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.2 }} className="border border-green-500/30 bg-green-500/5 p-4 mb-6 flex items-center gap-3">
          <Sparkles size={16} className="text-green-400 flex-shrink-0" />
          <div>
            <p className="font-mono text-xs text-green-400">BEST MATCH</p>
            <p className="font-mono text-sm text-white">{result.best_match}</p>
            <p className="font-mono text-[10px] text-white/30">{result.top_domain}</p>
          </div>
          <div className="ml-auto font-mono text-2xl text-green-400 font-bold">
            {(result.job_matches[0]?.match_score * 100).toFixed(0)}%
          </div>
        </motion.div>

        {/* Domain filter */}
        <div className="flex gap-2 flex-wrap mb-4">
          {domains.map(d => (
            <button key={d} onClick={() => setFilter(d)}
              className={`font-mono text-[10px] px-3 py-1 border transition-colors ${filter===d ? "border-white text-white" : "border-white/15 text-white/30 hover:border-white/40"}`}>
              {d}
            </button>
          ))}
        </div>

        {/* All job matches */}
        <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">ALL JOB MATCHES ({shown.length})</p>
        <div className="space-y-3">
          {shown.map((job, i) => (
            <motion.div key={job.job_id} initial={{ opacity:0, x:-10 }} animate={{ opacity:1, x:0 }} transition={{ delay:0.05*i }}
              className="border border-white/10 p-4 hover:border-white/25 transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-mono text-[10px] text-white/30 border border-white/10 px-1.5 py-0.5 mr-2">{job.domain}</span>
                  <span className="font-mono text-sm text-white">{job.job_title}</span>
                  <span className="font-mono text-xs text-white/30 ml-2">@ {job.company}</span>
                </div>
                <div className="text-right flex-shrink-0 ml-3">
                  <div className="font-mono text-lg text-white">{(job.match_score*100).toFixed(0)}%</div>
                  <div className={`font-mono text-[10px] ${job.recommendation==="Strong match"?"text-green-400":job.recommendation==="Good match"?"text-yellow-400":"text-white/30"}`}>{job.recommendation}</div>
                </div>
              </div>
              <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                <div className="h-full bg-white/60 rounded-full" style={{ width:`${job.match_score*100}%` }} />
              </div>
              <p className="font-mono text-[10px] text-white/30 mt-2">{job.keyword_hits}/{job.total_keywords} keywords matched</p>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Loading ───────────────────────────────────────────────────────────────────
function RealLoadingScreen({
  file, w1, w2, w3, topN, semantic, mode,
  onDone, onError,
}: {
  file: File; w1: number; w2: number; w3: number; topN: number; semantic: boolean; mode: UploadMode;
  onDone: (jobId: string, results: Candidate[]) => void;
  onError: (msg: string) => void;
}) {
  const [steps, setSteps] = useState<string[]>([]);
  const [pct, setPct] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    async function run() {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("skill_weight", String(w1));
      formData.append("semantic_weight", String(w2));
      formData.append("behavioral_weight", String(w3));
      formData.append("top_n", String(topN));
      formData.append("use_semantic", String(semantic));

      try {
        // kick off the job — returns job_id immediately
        const endpoint = mode === "bulk-pdf" ? `${API}/screen-bulk` : `${API}/rank`;
        const res = await fetch(endpoint, { method: "POST", body: formData });
        if (!res.ok) { const err = await res.json(); onError(err.detail || "Server error"); return; }
        const { job_id: jobId } = await res.json();

        // 2. poll /status/{job_id} every second until done or error
        let seenSteps = 0;
        while (true) {
          await new Promise((r) => setTimeout(r, 1000));

          const statusRes = await fetch(`${API}/status/${jobId}`);
          if (!statusRes.ok) { onError("Lost track of the job. Please try again."); return; }
          const status = await statusRes.json();

          // only append newly-seen steps so we don't duplicate them each poll
          if (status.steps && status.steps.length > seenSteps) {
            setSteps((s) => [...s, ...status.steps.slice(seenSteps)]);
            seenSteps = status.steps.length;
          }
          setPct(status.pct);

          if (status.status === "error") { onError(status.error || "Something went wrong"); return; }

          if (status.status === "done") {
            setPct(100);
            const preview = await fetch(`${API}/preview/${jobId}?limit=100`);
            const previewData = await preview.json();
            onDone(jobId, previewData.results);
            return;
          }
        }
      } catch (e: unknown) {
        onError(e instanceof Error ? e.message : "Cannot connect to backend. Make sure it is running on port 8000.");
      }
    }
    run();
  }, []);

  return <LoadingPage steps={steps.length ? steps : ["Connecting to backend..."]} pct={pct} />;
}

// ─── Results ──────────────────────────────────────────────────────────────────
function ResultsScreen({
  results,
  jobId,
  onBack,
  onAbout,
}: {
  results: Candidate[];
  jobId: string;
  onBack: () => void;
  onAbout: () => void;
}) {
  const [selectedJob, setSelectedJob] = useState(1);
  const [displayed, setDisplayed] = useState(results);

  // when user selects a different job on the radial, rescore
  const handleJobSelect = (id: number) => {
    setSelectedJob(id);
    setDisplayed(reScoreForJob(results, id));
  };

  const top3 = displayed.slice(0, 3);

  const top3Cards = top3.map((c, i) => ({
    icon: <Sparkles className="size-4 text-blue-300" />,
    title: `#${i + 1} — ${c.candidate_id}`,
    description: c.reasoning.split(";")[0],
    date: `Score: ${(c.score * 100).toFixed(1)}%`,
    titleClassName: i === 0 ? "text-yellow-400" : i === 1 ? "text-slate-300" : "text-amber-600",
  }));

  const downloadCSV = () => {
    if (jobId) {
      window.open(`${API}/download/${jobId}`, "_blank");
    } else {
      const rows = ["candidate_id,rank,score,reasoning", ...displayed.map((c) => `${c.candidate_id},${c.rank},${c.score},"${c.reasoning}"`)];
      const blob = new Blob([rows.join("\n")], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "submission.csv";
      a.click();
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      {/* Header */}
      <div className="border-b border-white/10 px-6 py-4 flex items-center justify-between sticky top-0 bg-neutral-950/90 backdrop-blur z-30">
        <button onClick={onBack} className="font-mono text-xs text-white/40 hover:text-white transition-colors">← new search</button>
        <h1 className="font-mono text-sm text-white/70 tracking-widest">RANKED CANDIDATES</h1>
        <div className="flex gap-2">
          <button onClick={onAbout} className="font-mono text-xs text-white/30 hover:text-white/60 transition-colors border border-white/10 px-3 py-1.5 hover:border-white/30">about</button>
          <button onClick={downloadCSV} className="font-mono text-xs border border-white/20 px-3 py-1.5 text-white/50 hover:border-white/50 hover:text-white transition-colors">download csv</button>
        </div>
      </div>

      <div className="flex">
        {/* Left — radial job selector */}
        <div className="w-80 flex-shrink-0 border-r border-white/10 relative" style={{ height: "calc(100vh - 57px)" }}>
          <div className="absolute top-3 left-0 right-0 text-center font-mono text-[10px] text-white/20 tracking-widest z-10">
            SELECT JOB TO RERANK
          </div>
          <div className="w-full h-full">
            <RadialOrbitalTimeline timelineData={JOB_DATA} onSelect={handleJobSelect} />
          </div>
          <div className="absolute bottom-3 left-0 right-0 text-center font-mono text-[9px] text-white/20">
            viewing: {JOB_DATA.find((j) => j.id === selectedJob)?.title}
          </div>
        </div>

        {/* Right — results */}
        <div className="flex-1 overflow-y-auto px-6 py-8" style={{ height: "calc(100vh - 57px)" }}>
          {/* Top 3 display cards */}
          <div className="mb-12">
            <p className="font-mono text-[10px] text-white/25 mb-6 tracking-widest">TOP 3 CANDIDATES</p>
            <div className="flex min-h-[260px] w-full items-center justify-center py-4">
              <div className="w-full max-w-xl">
                <DisplayCards cards={top3Cards} />
              </div>
            </div>
          </div>

          {/* Full list */}
          <div>
            <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">ALL RANKED ({displayed.length})</p>
            <div className="border border-white/10 overflow-hidden">
              <div className="grid grid-cols-[36px_160px_1fr_70px] gap-3 px-4 py-2 bg-white/5 font-mono text-[10px] text-white/25">
                <span>#</span><span>ID</span><span>REASONING</span><span>SCORE</span>
              </div>
              {displayed.map((c) => (
                <div key={c.candidate_id} className="grid grid-cols-[36px_160px_1fr_70px] gap-3 px-4 py-2.5 border-t border-white/5 hover:bg-white/5 transition-colors font-mono text-[10px]">
                  <span className="text-white/25">{c.rank}</span>
                  <span className="text-white/80">{c.candidate_id}</span>
                  <span className="text-white/35 truncate">{c.reasoning}</span>
                  <span className="text-white/60">{(c.score * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── About ─────────────────────────────────────────────────────────────────────
function AboutScreen({ onBack }: { onBack: () => void }) {
  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
        <button onClick={onBack} className="font-mono text-xs text-white/40 hover:text-white transition-colors">← back</button>
        <h1 className="font-mono text-sm text-white/70 tracking-widest">THE TEAM</h1>
        <div className="w-16" />
      </div>

      <div className="max-w-3xl mx-auto px-6 py-16">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <h2 className="font-handwritten text-6xl text-white mb-2">Who built this?</h2>
          <p className="font-mono text-xs text-white/30 mb-12 tracking-widest">
            REDROB DATA & AI CHALLENGE 2026 · MUIT NOIDA · B.TECH CSE (DATA SCIENCE)
          </p>
        </motion.div>

        <div className="grid gap-6">
          {TEAM.map((member, i) => (
            <motion.div
              key={member.name}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.15, duration: 0.5 }}
              className="border border-white/10 p-6 hover:border-white/25 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center font-mono text-xs text-white/60">
                      {i + 1}
                    </div>
                    <h3 className="font-handwritten text-3xl text-white">{member.name}</h3>
                  </div>
                  <p className="font-mono text-xs text-white/40 mb-1 ml-11">{member.role}</p>
                  <p className="font-mono text-[10px] text-white/20 mb-3 ml-11">{member.college} · {member.batch}</p>
                  <p className="font-mono text-xs text-white/50 ml-11 leading-relaxed">{member.bio}</p>
                </div>
                <div className="flex flex-col gap-2 flex-shrink-0">
                  <a href={member.github} target="_blank" rel="noopener noreferrer" className="text-white/25 hover:text-white transition-colors">
                    <GitBranch size={16} />
                  </a>
                  <a href={member.linkedin} target="_blank" rel="noopener noreferrer" className="text-white/25 hover:text-white transition-colors">
                    <ExternalLink size={16} />
                  </a>
                  <a href={`mailto:${member.email}`} className="text-white/25 hover:text-white transition-colors">
                    <Mail size={16} />
                  </a>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-12 border-t border-white/10 pt-8 text-center"
        >
          <p className="font-mono text-[10px] text-white/20 leading-loose">
            BUILT WITH: Python · FastAPI · sentence-transformers · Next.js · Framer Motion<br />
            SUPERVISOR: Dr. Kusum Lata · Dept. of Data Science & AI · MUIT
          </p>
        </motion.div>
      </div>
    </div>
  );
}

// ─── Error (auto-triggered only) ──────────────────────────────────────────────
function ErrorScreen({ message, onHome }: { message: string; onHome: () => void }) {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
      <NotFound1 onHome={onHome} />
      {message && (
        <p className="font-mono text-xs text-red-400 max-w-md text-center px-6 leading-relaxed">{message}</p>
      )}
    </div>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function Home() {
  const [screen, setScreen]           = useState<Screen>("boot");
  const [mode, setMode]               = useState<UploadMode>("jsonl");
  const [results, setResults]         = useState<Candidate[]>([]);
  const [jobId, setJobId]             = useState("");
  const [errorMsg, setErrorMsg]       = useState("");
  const [prevScreen, setPrevScreen]   = useState<Screen>("home");
  const [singleResult, setSingleResult] = useState<SingleResult | null>(null);
  const [uploadState, setUploadState] = useState<{
    file: File; w1: number; w2: number; w3: number; topN: number; semantic: boolean;
  } | null>(null);

  useEffect(() => {
    if (screen !== "boot") return;
    const handler = () => setScreen("home");
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [screen]);

  const goAbout = () => { setPrevScreen(screen); setScreen("about"); };
  const goBack  = () => setScreen(prevScreen);

  const handleModeSelect = (m: UploadMode) => {
    setMode(m);
    setScreen(m === "single-pdf" ? "single-upload" : "select");
  };

  const handleRun = (file: File, w1: number, w2: number, w3: number, topN: number, semantic: boolean) => {
    setUploadState({ file, w1, w2, w3, topN, semantic });
    setScreen("loading");
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div key={screen} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }} className="min-h-screen">
        {screen === "boot"          && <BootScreen onDone={() => setScreen("home")} />}
        {screen === "home"          && <HomeScreen onStart={() => setScreen("mode-select")} onAbout={goAbout} />}
        {screen === "mode-select"   && <ModeSelectScreen onSelect={handleModeSelect} onBack={() => setScreen("home")} />}
        {screen === "single-upload" && (
          <SinglePDFScreen
            onBack={() => setScreen("mode-select")}
            onResult={(data) => { setSingleResult(data); setScreen("single-result"); }}
            onError={(msg) => { setErrorMsg(msg); setScreen("error"); }}
          />
        )}
        {screen === "single-result" && singleResult && (
          <SingleResultScreen result={singleResult} onBack={() => setScreen("single-upload")} />
        )}
        {screen === "select"  && <SelectScreen mode={mode} onRun={handleRun} onBack={() => setScreen("mode-select")} />}
        {screen === "loading" && uploadState && (
          <RealLoadingScreen
            {...uploadState}
            mode={mode}
            onDone={(jid, res) => { setJobId(jid); setResults(res); setScreen("results"); }}
            onError={(msg) => { setErrorMsg(msg); setScreen("error"); }}
          />
        )}
        {screen === "results" && (
          <ResultsScreen results={results} jobId={jobId} onBack={() => setScreen("mode-select")} onAbout={goAbout} />
        )}
        {screen === "about" && <AboutScreen onBack={goBack} />}
        {screen === "error"  && <ErrorScreen message={errorMsg} onHome={() => { setErrorMsg(""); setScreen("home"); }} />}
      </motion.div>
    </AnimatePresence>
  );
}