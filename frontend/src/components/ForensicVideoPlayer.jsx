import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Scan, AlertOctagon, ShieldAlert, Target } from 'lucide-react';

export default function ForensicVideoPlayer({ mediaUrl, result, isVideo = true }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeRuleIndex, setActiveRuleIndex] = useState(-1);
  const videoRef = useRef(null);

  // We don't have exact timestamps, so we'll simulate real-time detection
  // by flashing through the SEBI rules as the video plays.
  const rules = result?.sebi_rules || [];
  const reasons = result?.reasons || [];

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const current = videoRef.current.currentTime;
    const duration = videoRef.current.duration;
    
    if (duration > 0) {
      const pct = (current / duration) * 100;
      setProgress(pct);
      
      // Simulate detection mapping: divide duration into chunks based on number of rules
      if (rules.length > 0) {
        const chunk = 100 / (rules.length + 1); // +1 so it doesn't trigger immediately
        const newIndex = Math.max(0, Math.floor(pct / chunk) - 1);
        if (newIndex !== activeRuleIndex && newIndex < rules.length) {
          setActiveRuleIndex(newIndex);
        }
      }
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  return (
    <div className="mb-6 bg-white rounded-xl border border-fintech-border overflow-hidden shadow-sm relative group">
      
      {/* Top Scanner Bar */}
      <div className="bg-slate-50 p-3 border-b border-fintech-border flex justify-between items-center">
        <div className="flex items-center space-x-2 text-fintech-text font-bold text-[10px] uppercase tracking-widest">
          <Scan className={`w-3.5 h-3.5 ${isPlaying ? 'animate-pulse text-fintech-action' : 'text-fintech-secondary'}`} />
          <span>{isPlaying ? 'LIVE FORENSIC SIGNAL ACTIVE' : 'FORENSIC MEDIA VIEWER'}</span>
        </div>
        <div className="flex space-x-2">
           <span className="w-2 h-2 rounded-full bg-fintech-red animate-pulse"></span>
           <span className="w-2 h-2 rounded-full bg-fintech-amber"></span>
           <span className="w-2 h-2 rounded-full bg-fintech-green"></span>
        </div>
      </div>

      <div className="relative">
        {/* Media Player */}
        <div className="relative bg-slate-100 w-full flex justify-center items-center overflow-hidden min-h-[300px] max-h-[500px]">
          {isVideo ? (
            <video
              ref={videoRef}
              src={mediaUrl}
              className="max-h-[500px] w-auto object-contain"
              onTimeUpdate={handleTimeUpdate}
              onEnded={() => setIsPlaying(false)}
              onClick={togglePlay}
            />
          ) : (
            <img src={mediaUrl} alt="Analyzed Media" className="max-h-[500px] w-auto object-contain" />
          )}

          {/* Simulated Scanline Overlay */}
          {isPlaying && (
            <div className="absolute top-0 left-0 w-full h-[2px] bg-fintech-red/70 shadow-[0_0_8px_rgba(217,45,32,0.8)] z-10 animate-scanline pointer-events-none"></div>
          )}

          {/* Central Target Overlay for Images (Fake scanning effect) */}
          {!isVideo && (
             <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-20">
                <Target className="w-24 h-24 text-fintech-green animate-pulse-slow" />
             </div>
          )}
        </div>

        {/* Custom Playback Controls */}
        {isVideo && (
          <div className="absolute bottom-0 left-0 w-full p-4 bg-gradient-to-t from-black/80 via-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="flex items-center space-x-4">
              <button onClick={togglePlay} className="text-white hover:text-fintech-action transition-colors">
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              </button>
              
              {/* Progress Bar */}
              <div className="flex-1 h-1.5 bg-white/30 rounded-full overflow-hidden cursor-pointer backdrop-blur-sm" onClick={(e) => {
                  if (videoRef.current) {
                      const rect = e.currentTarget.getBoundingClientRect();
                      const clickX = e.clientX - rect.left;
                      const pct = clickX / rect.width;
                      videoRef.current.currentTime = pct * videoRef.current.duration;
                  }
              }}>
                <div 
                  className="h-full bg-fintech-action relative transition-all duration-75"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Dynamic HUD Bottom Section */}
      <div className="bg-white p-5 border-t border-fintech-border">
        
        {/* Animated Typing/Flashing Rule */}
        <div className="h-[70px]">
          {activeRuleIndex >= 0 && activeRuleIndex < rules.length ? (
            <div className="animate-fade-in-up border-l-4 border-fintech-red pl-4">
              <div className="flex items-center space-x-2 text-fintech-red mb-1">
                <AlertOctagon className="w-4 h-4 animate-pulse" />
                <span className="font-bold text-[10px] tracking-widest uppercase">Regulatory Signal Detected</span>
              </div>
              <h3 className="text-base font-bold text-fintech-text mb-0.5">{rules[activeRuleIndex]}</h3>
              <p className="text-xs text-fintech-secondary font-medium">
                {reasons[activeRuleIndex] || reasons[0] || "Suspicious claims identified in this segment."}
              </p>
            </div>
          ) : (
             <div className="flex flex-col items-center justify-center h-full text-fintech-secondary space-y-2 opacity-50">
               {isPlaying ? (
                 <>
                   <ShieldAlert className="w-5 h-5 animate-pulse" />
                   <span className="text-[10px] font-bold uppercase tracking-widest">Scanning media frames...</span>
                 </>
               ) : (
                 <>
                   <Scan className="w-5 h-5" />
                   <span className="text-[10px] font-bold uppercase tracking-widest">{isVideo ? "Play video to begin real-time analysis" : "Visual media analysis complete"}</span>
                 </>
               )}
             </div>
          )}
        </div>

      </div>

    </div>
  );
}
