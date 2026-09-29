"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

const FUNNY_MESSAGES = [
  "Convincing the hamsters to run faster...",
  "Loading... because teleportation isn't invented yet.",
  "Reticulating splines.",
  "Counting to infinity... 42% complete.",
  "Summoning ancient code spirits...",
  "Please wait while we pretend this is taking longer for dramatic effect.",
  "Loading your stuff. Not our stuff. We know where ours is.",
  "Downloading more RAM...",
  "Teaching the AI the difference between 'their' and 'there'...",
  "The internet is thinking really hard right now.",
  "One moment... the electrons are lining up.",
  "Loading... definitely not stuck.",
  "Generating excuses for the loading time...",
  "Please hold. The ducks are not yet in a row.",
  "Making sure everything is broken equally.",
  "Fetching your data from the void...",
  "Powered by caffeine and questionable decisions.",
  "Almost there. Probably.",
  "Loading... if this takes too long, blame physics.",
  "Compiling bugs into features...",
  "Please wait. We're converting coffee into code.",
];

function TypingMessage({ text }: { text: string }) {
  const [displayed, setDisplayed] = useState("");
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    setDisplayed("");
    setIdx(0);
  }, [text]);

  useEffect(() => {
    if (idx >= text.length) return;
    const timer = setTimeout(() => {
      setDisplayed((d) => d + text[idx]);
      setIdx((i) => i + 1);
    }, 28);
    return () => clearTimeout(timer);
  }, [idx, text]);

  return (
    <span>
      {displayed}
      {idx < text.length && (
        <span className="inline-block w-0.5 h-3 bg-white/50 ml-0.5 animate-pulse" />
      )}
    </span>
  );
}

interface LoadingPageProps {
  steps: string[];
  pct?: number;
}

export default function LoadingPage({ steps, pct = 0 }: LoadingPageProps) {
  const [funnyMsg, setFunnyMsg] = useState(FUNNY_MESSAGES[0]);
  const [msgIndex, setMsgIndex] = useState(0);
  const [showMsg, setShowMsg] = useState(true);

  // rotate funny message every 3.5s
  useEffect(() => {
    const timer = setInterval(() => {
      setShowMsg(false);
      setTimeout(() => {
        setMsgIndex((i) => {
          const next = (i + 1) % FUNNY_MESSAGES.length;
          setFunnyMsg(FUNNY_MESSAGES[next]);
          return next;
        });
        setShowMsg(true);
      }, 400);
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-full h-screen bg-black relative overflow-hidden flex items-center justify-center">
      {/* Animated background */}
      <div className="absolute inset-0">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            background:
              "radial-gradient(ellipse at 20% 50%, #1a1a2e 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, #16213e 0%, transparent 50%), radial-gradient(ellipse at 50% 80%, #0f3460 0%, transparent 50%)",
          }}
        />
        <motion.div
          className="absolute inset-0"
          style={{
            background:
              "repeating-linear-gradient(0deg, transparent, transparent 40px, rgba(255,255,255,0.008) 40px, rgba(255,255,255,0.008) 41px), repeating-linear-gradient(90deg, transparent, transparent 40px, rgba(255,255,255,0.008) 40px, rgba(255,255,255,0.008) 41px)",
          }}
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 3, repeat: Infinity }}
        />
      </div>

      {/* Glow blobs */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          className="absolute top-1/4 left-1/3 w-40 h-40 bg-indigo-900/20 rounded-full blur-3xl"
          animate={{ opacity: [0.3, 0.7, 0.3], scale: [1, 1.2, 1] }}
          transition={{ duration: 3, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-1/3 right-1/4 w-32 h-32 bg-blue-900/15 rounded-full blur-2xl"
          animate={{ opacity: [0.2, 0.5, 0.2], scale: [1, 1.3, 1] }}
          transition={{ duration: 2, repeat: Infinity, delay: 1 }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-md px-8 text-center">

        {/* Spinning ring */}
        <div className="flex justify-center mb-10">
          <div className="relative w-28 h-28">
            <motion.div
              className="absolute inset-0 rounded-full border border-white/15"
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            />
            <motion.div
              className="absolute inset-3 rounded-full border border-white/10"
              animate={{ rotate: -360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
            <motion.div
              className="absolute inset-6 rounded-full border border-white/5"
              animate={{ rotate: 360 }}
              transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-white/50 font-mono text-sm">{pct}%</span>
            </div>
            {/* Orbiting dot */}
            <motion.div
              className="absolute top-0 left-1/2 w-2 h-2 bg-white/70 rounded-full -translate-x-1/2 -translate-y-1"
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              style={{ transformOrigin: "50% 56px" }}
            />
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-px bg-white/10 mb-8 overflow-hidden">
          <motion.div
            className="h-full bg-white/50"
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>

        {/* Funny rotating message */}
        <div className="mb-6 min-h-[32px] flex items-center justify-center">
          <AnimatePresence mode="wait">
            {showMsg && (
              <motion.p
                key={msgIndex}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.3 }}
                className="font-mono text-xs text-white/60 text-center leading-relaxed"
              >
                <TypingMessage text={funnyMsg} />
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        {/* Real pipeline steps */}
        <div className="space-y-1 max-h-36 overflow-hidden">
          {steps.slice(-6).map((step, i, arr) => (
            <motion.div
              key={step + i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: i === arr.length - 1 ? 0.7 : 0.2, x: 0 }}
              transition={{ duration: 0.3 }}
              className="font-mono text-[10px] text-white/40 text-left"
            >
              {i === arr.length - 1 ? "▸ " : "  "}{step}
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
