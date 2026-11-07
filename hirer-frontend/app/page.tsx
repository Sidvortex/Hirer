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

type Screen = "boot" | "home" | "mode-select" | "select" | "loading" | "results" | "single-upload" | "single-form" | "single-result" | "bulk-extract" | "bulk-review" | "bulk-rank" | "about" | "error";
type UploadMode = "jsonl" | "single-pdf" | "bulk-pdf";

interface Candidate {
  candidate_id: string;
  rank: number;
  score: number;
  reasoning: string;
  name?: string;
  skill?: number;
  semantic?: number;
  behavioral?: number;
  matched_skills?: string[];
}

interface RankMeta {
  total_candidates: number;
  weights_used: { skill: number; semantic: number; behavioral: number };
  reference_date: string;
  job_title: string;
  relative?: boolean;
}

interface JobMatch {
  job_id: number;
  domain: string;
  job_title: string;
  company: string;
  match_score: number;
  keyword_hits: number;
  total_keywords: number;
  matched_keywords?: string[];
  wanted_role?: boolean;
  recommendation: string;
}

interface ExtractedResume {
  candidate_id: string;
  file: string;
  name: string;
  current_title: string;
  years_of_experience: number;
  skills: string[];
  location: string;
  notice_period_days: number | null;
  open_to_work: boolean | null;
  willing_to_relocate: boolean | null;
  has_details: boolean;
  details_source: string | null;
}

interface SingleExtract {
  candidate: Record<string, unknown>;
  fields: ExtractedResume;
}

// what the form sends back; empty strings mean "leave as extracted / unknown"
interface ResumeEdits {
  name: string;
  current_title: string;
  years_of_experience: string;
  skills: string[];
  location: string;
  notice_period_days: string;
  open_to_work: string;
  willing_to_relocate: string;
  expected_role?: string;
}

interface SingleResult {
  candidate: {
    name: string; current_title: string; years_of_experience: number; skills_found: string[]; location: string; industry: string;
    notice_period_days?: number | null; willing_to_relocate?: boolean | null; expected_role?: string;
  };
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

// ─── Boot ─────────────────────────────────────────────────────────────────────
function BootScreen({ onDone }: { onDone: () => void }) {
  // silently wake up the backend while the animation plays (hosted instances may be asleep)
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
function downloadDetailsTemplate() {
  const csv = [
    "file,notice_period_days,open_to_work,location,willing_to_relocate",
    "asha_rao.pdf,30,yes,Pune,no",
    "ravi_kumar.pdf,90,no,Bangalore,yes",
  ].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = "details.csv";
  a.click();
}

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
          {mode === "bulk-pdf" && (
            <div className="font-mono text-[10px] text-white/35 leading-relaxed border border-white/10 px-3 py-2">
              Optional: add each candidate&apos;s notice period, location and so on, either as a file with the same name
              (asha.pdf + asha.txt) or one details.csv for everyone.{" "}
              <button type="button" onClick={downloadDetailsTemplate} className="underline hover:text-white">download template</button>.
              Resumes without details get a short form after upload.
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
  onResult: (data: SingleExtract) => void;
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
      const res = await fetch(`${API}/extract-single`, { method: "POST", body: fd });
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
          <p className="font-mono text-xs text-white/30 mb-2 tracking-widest">WE&apos;LL MATCH YOU AGAINST 20 JOB ROLES</p>
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
            {loading ? <><Loader2 size={14} className="animate-spin" /> Reading resume...</> : !file ? "↑ UPLOAD YOUR RESUME FIRST" : "NEXT: CHECK YOUR DETAILS →"}
          </button>
        </motion.div>
      </div>
    </div>
  );
}

// ─── Shared form bits ─────────────────────────────────────────────────────────
const inputCls = "w-full bg-transparent border border-white/15 focus:border-white/50 outline-none px-2 py-1.5 font-mono text-xs text-white placeholder:text-white/20";

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="block font-mono text-[10px] text-white/35 mb-1 tracking-widest">{label}</span>
      {children}
      {hint && <span className="block font-mono text-[9px] text-white/20 mt-1">{hint}</span>}
    </label>
  );
}

const boolStr = (b: boolean | null | undefined) => (b === true ? "yes" : b === false ? "no" : "");

function editsFrom(r: ExtractedResume): ResumeEdits {
  return {
    name: r.name,
    current_title: r.current_title,
    years_of_experience: r.years_of_experience ? String(r.years_of_experience) : "",
    skills: r.skills,
    location: r.location,
    notice_period_days: r.notice_period_days === null ? "" : String(r.notice_period_days),
    open_to_work: boolStr(r.open_to_work),
    willing_to_relocate: boolStr(r.willing_to_relocate),
  };
}

function NoticeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={`${inputCls} bg-neutral-950`}>
      <option value="">not given</option>
      <option value="0">immediate</option>
      <option value="15">15 days</option>
      <option value="30">30 days</option>
      <option value="60">60 days</option>
      <option value="90">90 days</option>
      <option value="120">more than 90 days</option>
    </select>
  );
}

function YesNo({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-1">
      {[["yes", "yes"], ["no", "no"], ["", "—"]].map(([v, label]) => (
        <button key={label} type="button" onClick={() => onChange(v)}
          className={`flex-1 font-mono text-[10px] py-1.5 border transition-colors ${value === v ? "border-white text-white" : "border-white/15 text-white/30 hover:border-white/40"}`}>
          {label}
        </button>
      ))}
    </div>
  );
}

function SkillChips({ skills, onChange }: { skills: string[]; onChange: (s: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const parts = draft.split(",").map((x) => x.trim()).filter(Boolean)
      .filter((x) => !skills.some((s) => s.toLowerCase() === x.toLowerCase()));
    if (parts.length) onChange([...skills, ...parts]);
    setDraft("");
  };
  return (
    <div className="border border-white/15 p-2">
      <div className="flex flex-wrap gap-1.5 mb-2">
        {skills.map((s) => (
          <span key={s} className="font-mono text-[10px] border border-white/20 text-white/60 pl-2 pr-1 py-0.5 flex items-center gap-1">
            {s}
            <button type="button" onClick={() => onChange(skills.filter((x) => x !== s))} className="text-white/30 hover:text-red-400 px-1">×</button>
          </span>
        ))}
        {!skills.length && <span className="font-mono text-[10px] text-white/20">no skills found, add some below</span>}
      </div>
      <input value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
        onBlur={add} placeholder="add a skill and press Enter" className={inputCls} />
    </div>
  );
}

// ─── Single: check your details (before matching) ─────────────────────────────
const ROLE_OPTIONS = [
  "Senior AI Engineer", "ML Platform Engineer", "NLP Researcher", "Data Scientist", "Backend Engineer",
  "Frontend Developer", "Android Developer", "iOS Developer", "Flutter Developer", "DevOps Engineer",
  "Cloud Architect", "Site Reliability Engineer", "Full Stack Developer", "Data Engineer", "Business Analyst",
  "Cybersecurity Analyst", "Product Manager", "UI/UX Designer", "Financial Analyst", "Digital Marketing Manager",
];

function SingleFormScreen({ extracted, onBack, onResult, onError }: {
  extracted: SingleExtract;
  onBack: () => void;
  onResult: (r: SingleResult) => void;
  onError: (msg: string) => void;
}) {
  const [f, setF] = useState<ResumeEdits>({ ...editsFrom(extracted.fields), expected_role: "" });
  const [loading, setLoading] = useState(false);
  const set = (k: keyof ResumeEdits) => (v: string) => setF((x) => ({ ...x, [k]: v }));

  const submit = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/match-single`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate: extracted.candidate, edits: f }),
      });
      if (!res.ok) { const err = await res.json(); onError(err.detail || "Failed"); return; }
      onResult(await res.json());
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Cannot connect to backend");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white px-6 py-10">
      <div className="max-w-xl mx-auto">
        <button onClick={onBack} className="font-mono text-xs text-white/30 hover:text-white transition-colors mb-8 block">← back</button>
        <h2 className="font-handwritten text-5xl text-white mb-2">Check your details</h2>
        <p className="font-mono text-[10px] text-white/30 mb-8 leading-relaxed">
          We filled this in from {extracted.fields.file || "your resume"}. Fix anything we got wrong and add what a resume
          doesn&apos;t say. Only the fields you can see are used.
        </p>

        <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">FROM YOUR RESUME</p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <Field label="NAME"><input className={inputCls} value={f.name} onChange={(e) => set("name")(e.target.value)} /></Field>
          <Field label="CURRENT TITLE"><input className={inputCls} value={f.current_title} onChange={(e) => set("current_title")(e.target.value)} /></Field>
          <Field label="YEARS OF EXPERIENCE"><input className={inputCls} type="number" min={0} step={0.5} value={f.years_of_experience} onChange={(e) => set("years_of_experience")(e.target.value)} /></Field>
          <Field label="CURRENT LOCATION"><input className={inputCls} value={f.location} placeholder="e.g. Noida" onChange={(e) => set("location")(e.target.value)} /></Field>
        </div>
        <div className="mb-8">
          <Field label="SKILLS"><SkillChips skills={f.skills} onChange={(s) => setF((x) => ({ ...x, skills: s }))} /></Field>
        </div>

        <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">NOT ON YOUR RESUME</p>
        <div className="grid grid-cols-2 gap-4 mb-10">
          <Field label="ROLE YOU WANT" hint="matching roles get a small boost">
            <input className={inputCls} list="hirer-roles" value={f.expected_role} placeholder="e.g. Data Scientist" onChange={(e) => set("expected_role")(e.target.value)} />
            <datalist id="hirer-roles">{ROLE_OPTIONS.map((r) => <option key={r} value={r} />)}</datalist>
          </Field>
          <Field label="NOTICE PERIOD"><NoticeSelect value={f.notice_period_days} onChange={set("notice_period_days")} /></Field>
          <Field label="OPEN TO RELOCATE"><YesNo value={f.willing_to_relocate} onChange={set("willing_to_relocate")} /></Field>
        </div>

        <button onClick={submit} disabled={loading}
          className="w-full bg-white text-black font-mono text-sm py-3 hover:bg-white/90 disabled:opacity-25 transition-colors flex items-center justify-center gap-2">
          {loading ? <><Loader2 size={14} className="animate-spin" /> Matching...</> : "FIND MY BEST JOB MATCH →"}
        </button>
      </div>
    </div>
  );
}

// ─── Bulk: review the resumes that still need details ─────────────────────────
function BulkReviewScreen({ resumes, skipped, onBack, onRank }: {
  resumes: ExtractedResume[];
  skipped: string[];
  onBack: () => void;
  onRank: (edits: Record<string, ResumeEdits>) => void;
}) {
  const [edits, setEdits] = useState<Record<string, ResumeEdits>>(
    () => Object.fromEntries(resumes.map((r) => [r.candidate_id, editsFrom(r)])));
  const [showDone, setShowDone] = useState(false);
  const needs = resumes.filter((r) => !r.has_details);
  const done = resumes.filter((r) => r.has_details);
  const set = (id: string, k: keyof ResumeEdits, v: string) =>
    setEdits((e) => ({ ...e, [id]: { ...e[id], [k]: v } }));
  const filled = needs.filter((r) => {
    const e = edits[r.candidate_id];
    return e.notice_period_days || e.open_to_work || e.location || e.willing_to_relocate;
  }).length;

  const row = (r: ExtractedResume) => {
    const e = edits[r.candidate_id];
    return (
      <div key={r.candidate_id} className="border border-white/10 p-4">
        <div className="flex items-baseline justify-between mb-3 gap-3">
          <div className="min-w-0">
            <span className="font-handwritten text-2xl text-white mr-3">{e.name || "Unknown name"}</span>
            <span className="font-mono text-[10px] text-white/30 truncate">{r.file}</span>
          </div>
          {r.has_details
            ? <span className="font-mono text-[10px] text-green-400/80 flex-shrink-0">✓ details from {r.details_source}</span>
            : <span className="font-mono text-[10px] text-yellow-500/70 flex-shrink-0">needs details</span>}
        </div>
        <div className="grid grid-cols-4 gap-3 mb-3">
          <Field label="NAME"><input className={inputCls} value={e.name} onChange={(x) => set(r.candidate_id, "name", x.target.value)} /></Field>
          <Field label="TITLE"><input className={inputCls} value={e.current_title} onChange={(x) => set(r.candidate_id, "current_title", x.target.value)} /></Field>
          <Field label="YEARS EXP"><input className={inputCls} type="number" min={0} step={0.5} value={e.years_of_experience} onChange={(x) => set(r.candidate_id, "years_of_experience", x.target.value)} /></Field>
          <Field label="LOCATION"><input className={inputCls} value={e.location} onChange={(x) => set(r.candidate_id, "location", x.target.value)} /></Field>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="NOTICE PERIOD"><NoticeSelect value={e.notice_period_days} onChange={(v) => set(r.candidate_id, "notice_period_days", v)} /></Field>
          <Field label="OPEN TO WORK"><YesNo value={e.open_to_work} onChange={(v) => set(r.candidate_id, "open_to_work", v)} /></Field>
          <Field label="WILL RELOCATE"><YesNo value={e.willing_to_relocate} onChange={(v) => set(r.candidate_id, "willing_to_relocate", v)} /></Field>
        </div>
        <p className="font-mono text-[9px] text-white/25 mt-3 truncate">
          skills found: {r.skills.length ? r.skills.join(", ") : "none"}
        </p>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <div className="border-b border-white/10 px-6 py-4 flex items-center justify-between sticky top-0 bg-neutral-950/90 backdrop-blur z-30">
        <button onClick={onBack} className="font-mono text-xs text-white/40 hover:text-white transition-colors">← upload again</button>
        <h1 className="font-mono text-sm text-white/70 tracking-widest">ADD CANDIDATE DETAILS</h1>
        <div className="w-24" />
      </div>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <p className="font-mono text-xs text-white/50 mb-1">
          {resumes.length} resumes read · {done.length} already have details · {needs.length} need details
        </p>
        <p className="font-mono text-[10px] text-white/25 mb-6 leading-relaxed">
          Resumes don&apos;t say when someone can join or where they&apos;ll work. Fill in what you know; blanks count as
          neutral, not as a minus. Check the name, title and years too: those come from automatic extraction.
        </p>

        {skipped.length > 0 && (
          <div className="flex items-start gap-2 border border-red-500/20 bg-red-500/5 px-3 py-2 mb-6">
            <AlertTriangle size={11} className="text-red-400/70 flex-shrink-0 mt-0.5" />
            <span className="font-mono text-[10px] text-red-400/70">Couldn&apos;t read any text from: {skipped.join(", ")}</span>
          </div>
        )}

        <div className="space-y-3 mb-6">{needs.map(row)}</div>

        {done.length > 0 && (
          <div className="mb-8">
            <button onClick={() => setShowDone((v) => !v)} className="font-mono text-[10px] text-white/30 hover:text-white/60 tracking-widest mb-3">
              {showDone ? "▾" : "▸"} {done.length} WITH DETAILS FROM FILES
            </button>
            {showDone && <div className="space-y-3">{done.map(row)}</div>}
          </div>
        )}

        <div className="sticky bottom-0 bg-neutral-950/95 backdrop-blur py-4 border-t border-white/10 flex items-center gap-4">
          <span className="font-mono text-[10px] text-white/30 flex-1">{filled}/{needs.length} filled in</span>
          <button onClick={() => onRank(edits)}
            className="bg-white text-black font-mono text-sm px-6 py-3 hover:bg-white/90 transition-colors">
            RANK {resumes.length} RESUMES →
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Generic background job: start it, poll /status, hand back the job id ─────
function JobScreen({ start, onDone, onError }: {
  start: () => Promise<Response>;
  onDone: (jobId: string) => Promise<void> | void;
  onError: (msg: string) => void;
}) {
  const [steps, setSteps] = useState<string[]>([]);
  const [pct, setPct] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const res = await start();
        if (!res.ok) { const err = await res.json(); onError(err.detail || "Server error"); return; }
        const { job_id: jobId } = await res.json();
        let seen = 0;
        while (true) {
          await new Promise((r) => setTimeout(r, 1000));
          const sr = await fetch(`${API}/status/${jobId}`);
          if (!sr.ok) { onError("Lost track of the job. Please try again."); return; }
          const st = await sr.json();
          if (st.steps && st.steps.length > seen) {
            setSteps((s) => [...s, ...st.steps.slice(seen)]);
            seen = st.steps.length;
          }
          setPct(st.pct);
          if (st.status === "error") { onError(st.error || "Something went wrong"); return; }
          if (st.status === "done") { setPct(100); await onDone(jobId); return; }
        }
      } catch (e: unknown) {
        onError(e instanceof Error ? e.message : "Cannot connect to backend. Make sure it is running on port 8000.");
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <LoadingPage steps={steps.length ? steps : ["Connecting to backend..."]} pct={pct} />;
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
          <p className="font-mono text-xs text-white/50 mb-1">{[c.current_title, c.years_of_experience ? `${Number(c.years_of_experience).toFixed(1)} yrs` : "experience not given", c.industry].filter(Boolean).join(" · ")}</p>
          <p className="font-mono text-[10px] text-white/30 mb-3">
            {[c.location,
              c.notice_period_days != null && (c.notice_period_days === 0 ? "can join immediately" : `${c.notice_period_days}-day notice`),
              c.willing_to_relocate === true && "open to relocate",
              c.willing_to_relocate === false && "not relocating",
              c.expected_role && `wants: ${c.expected_role}`].filter(Boolean).join(" · ")}
          </p>
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
              <p className="font-mono text-[10px] text-white/30 mt-2">
                {job.keyword_hits}/{job.total_keywords} keywords matched{job.matched_keywords?.length ? `: ${job.matched_keywords.join(", ")}` : ""}
                {job.wanted_role && <span className="text-green-400/70"> · the role you want</span>}
              </p>
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
  onDone: (jobId: string, results: Candidate[], meta: RankMeta | null) => void;
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
        const res = await fetch(`${API}/rank`, { method: "POST", body: formData });
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
            onDone(jobId, previewData.results, previewData.meta ?? null);
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
  meta,
  onBack,
  onAbout,
}: {
  results: Candidate[];
  jobId: string;
  meta: RankMeta | null;
  onBack: () => void;
  onAbout: () => void;
}) {
  const displayed = results;
  const job = JOB_DATA[0];
  const pct = (x?: number) => (x === undefined ? "–" : `${Math.round(x * 100)}`);

  const top3 = displayed.slice(0, 3);

  const top3Cards = top3.map((c, i) => ({
    icon: <Sparkles className="size-4 text-blue-300" />,
    title: `#${i + 1} — ${c.name || c.candidate_id}`,
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
        {/* Left — what this ranking was scored against */}
        <div className="w-80 flex-shrink-0 border-r border-white/10 px-6 py-8 overflow-y-auto" style={{ height: "calc(100vh - 57px)" }}>
          <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">SCORED AGAINST</p>
          <h2 className="font-mono text-sm text-white mb-1">{meta?.job_title ?? job.title}</h2>
          <p className="font-mono text-[10px] text-white/40 leading-relaxed mb-8">{job.content}</p>

          {meta && (
            <>
              <p className="font-mono text-[10px] text-white/25 mb-3 tracking-widest">WEIGHTS USED</p>
              {(["skill", "semantic", "behavioral"] as const).map((k) => (
                <div key={k} className="mb-3">
                  <div className="flex justify-between font-mono text-[10px] text-white/50 mb-1">
                    <span>{k}</span><span>{Math.round(meta.weights_used[k] * 100)}%</span>
                  </div>
                  <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full bg-white/60 rounded-full" style={{ width: `${meta.weights_used[k] * 100}%` }} />
                  </div>
                </div>
              ))}
              <p className="font-mono text-[9px] text-white/25 leading-relaxed mt-4">
                When semantic matching is off its weight goes to skill. Resumes with no availability details
                can&apos;t be compared on availability, so that weight moves to skill too.
              </p>
              <p className="font-mono text-[9px] text-white/25 leading-relaxed mt-4">
                {meta.total_candidates.toLocaleString()} candidates ·{" "}
                {meta.relative === false
                  ? "scores are absolute: 100% would be a perfect fit, however many resumes you upload"
                  : `scores are relative to this file · activity measured from ${meta.reference_date}`}
              </p>
            </>
          )}
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
              <div className="grid grid-cols-[36px_160px_1fr_110px_70px] gap-3 px-4 py-2 bg-white/5 font-mono text-[10px] text-white/25">
                <span>#</span><span>{displayed[0]?.name ? "NAME" : "ID"}</span><span>REASONING</span><span title="skill / semantic / behavioral, 0-100 within this batch">SKL / SEM / BEH</span><span>SCORE</span>
              </div>
              {displayed.map((c) => (
                <div key={c.candidate_id} className="grid grid-cols-[36px_160px_1fr_110px_70px] gap-3 px-4 py-2.5 border-t border-white/5 hover:bg-white/5 transition-colors font-mono text-[10px]">
                  <span className="text-white/25">{c.rank}</span>
                  <span className="text-white/80 truncate">{c.name || c.candidate_id}</span>
                  <span className="text-white/35 truncate" title={c.matched_skills?.length ? `matched: ${c.matched_skills.join(", ")}` : undefined}>{c.reasoning}</span>
                  <span className="text-white/40">{pct(c.skill)} / {pct(c.semantic)} / {pct(c.behavioral)}</span>
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
  const [meta, setMeta]               = useState<RankMeta | null>(null);
  const [errorMsg, setErrorMsg]       = useState("");
  const [prevScreen, setPrevScreen]   = useState<Screen>("home");
  const [singleResult, setSingleResult] = useState<SingleResult | null>(null);
  const [singleExtract, setSingleExtract] = useState<SingleExtract | null>(null);
  const [extractId, setExtractId]     = useState("");
  const [extracted, setExtracted]     = useState<{ resumes: ExtractedResume[]; skipped: string[] } | null>(null);
  const [bulkEdits, setBulkEdits]     = useState<Record<string, ResumeEdits>>({});
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
    setScreen(mode === "bulk-pdf" ? "bulk-extract" : "loading");
  };

  const fail = (msg: string) => { setErrorMsg(msg); setScreen("error"); };

  const loadResults = async (jid: string) => {
    const r = await fetch(`${API}/preview/${jid}?limit=100`);
    const data = await r.json();
    setJobId(jid); setResults(data.results); setMeta(data.meta ?? null); setScreen("results");
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
            onResult={(data) => { setSingleExtract(data); setScreen("single-form"); }}
            onError={fail}
          />
        )}
        {screen === "single-form" && singleExtract && (
          <SingleFormScreen
            extracted={singleExtract}
            onBack={() => setScreen("single-upload")}
            onResult={(data) => { setSingleResult(data); setScreen("single-result"); }}
            onError={fail}
          />
        )}
        {screen === "bulk-extract" && uploadState && (
          <JobScreen
            start={() => { const fd = new FormData(); fd.append("file", uploadState.file); return fetch(`${API}/extract-bulk`, { method: "POST", body: fd }); }}
            onDone={async (jid) => {
              const data = await (await fetch(`${API}/extracted/${jid}`)).json();
              setExtractId(jid); setExtracted(data); setBulkEdits({});
              // every resume already has a detail file: nothing to ask, rank straight away
              setScreen(data.resumes.every((r: ExtractedResume) => r.has_details) ? "bulk-rank" : "bulk-review");
            }}
            onError={fail}
          />
        )}
        {screen === "bulk-review" && extracted && (
          <BulkReviewScreen
            resumes={extracted.resumes}
            skipped={extracted.skipped}
            onBack={() => setScreen("select")}
            onRank={(edits) => { setBulkEdits(edits); setScreen("bulk-rank"); }}
          />
        )}
        {screen === "bulk-rank" && uploadState && (
          <JobScreen
            start={() => fetch(`${API}/rank-bulk`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                extract_job_id: extractId, edits: bulkEdits,
                skill_weight: uploadState.w1, semantic_weight: uploadState.w2, behavioral_weight: uploadState.w3,
                top_n: uploadState.topN, use_semantic: uploadState.semantic,
              }),
            })}
            onDone={loadResults}
            onError={fail}
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
            onDone={(jid, res, m) => { setJobId(jid); setResults(res); setMeta(m); setScreen("results"); }}
            onError={(msg) => { setErrorMsg(msg); setScreen("error"); }}
          />
        )}
        {screen === "results" && (
          <ResultsScreen results={results} jobId={jobId} meta={meta} onBack={() => setScreen("mode-select")} onAbout={goAbout} />
        )}
        {screen === "about" && <AboutScreen onBack={goBack} />}
        {screen === "error"  && <ErrorScreen message={errorMsg} onHome={() => { setErrorMsg(""); setScreen("home"); }} />}
      </motion.div>
    </AnimatePresence>
  );
}