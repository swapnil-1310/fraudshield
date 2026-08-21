import React from 'react';
import { AlertOctagon, CheckCircle2, Cpu, AlertTriangle, ShieldCheck, FileText, Scale, Activity, Bug, BadgeCheck, Info } from 'lucide-react';
import ForensicVideoPlayer from './ForensicVideoPlayer';

const SCHEME_LABEL = {
  pump_dump: { label: 'Pump & Dump', color: 'text-red-400 bg-red-500/10 border-red-500/30' },
  ponzi: { label: 'Ponzi / Pyramid', color: 'text-orange-400 bg-orange-500/10 border-orange-500/30' },
  insider_tip: { label: 'Insider Tip', color: 'text-purple-400 bg-purple-500/10 border-purple-500/30' },
  paid_group: { label: 'Unregistered Paid Group', color: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  impersonation: { label: 'Advisor Impersonation', color: 'text-pink-400 bg-pink-500/10 border-pink-500/30' },
  none: null,
};

const CONFIDENCE_BADGE = {
  HIGH:   'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  MEDIUM: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  LOW:    'bg-slate-500/15 text-slate-300 border-slate-500/30',
};

export default function DualVerdictCard({ result }) {
  if (!result) return null;

  const getVerdictTheme = () => {
    switch (result.dual_verdict) {
      case 'AI_SEBI_VIOLATION':
        return {
          bg: 'bg-white', border: 'border-fintech-red/30 border-t-4 border-t-fintech-red',
          badgeBg: 'bg-red-50 text-fintech-red border-red-200',
          icon: AlertOctagon, iconColor: 'text-fintech-red bg-red-50',
          title: 'HIGH RISK SCAM DETECTED'
        };
      case 'AI_SEBI_COMPLIANT':
        return {
          bg: 'bg-white', border: 'border-fintech-blue/30 border-t-4 border-t-fintech-blue',
          badgeBg: 'bg-blue-50 text-fintech-blue border-blue-200',
          icon: Cpu, iconColor: 'text-fintech-blue bg-blue-50',
          title: 'AI MEDIA DETECTED (SEBI COMPLIANT)'
        };
      case 'REAL_SEBI_VIOLATION':
        return {
          bg: 'bg-white', border: 'border-fintech-amber/30 border-t-4 border-t-fintech-amber',
          badgeBg: 'bg-amber-50 text-fintech-amber border-amber-200',
          icon: AlertTriangle, iconColor: 'text-fintech-amber bg-amber-50',
          title: 'SEBI REGULATORY VIOLATION'
        };
      default:
        return {
          bg: 'bg-white', border: 'border-fintech-green/30 border-t-4 border-t-fintech-green',
          badgeBg: 'bg-fintech-soft text-fintech-green border-fintech-green/20',
          icon: ShieldCheck, iconColor: 'text-fintech-green bg-fintech-soft',
          title: 'SAFE & SEBI VERIFIED'
        };
    }
  };

  const theme = getVerdictTheme();
  const HeaderIcon = theme.icon;
  const schemes = (result.detected_schemes || []).filter(s => s !== 'none');
  const complianceSignals = result.compliance_signals || [];
  const confidence = result.confidence || 'MEDIUM';
  const mediaUrl = result.videoUrl || result.imageUrl;
  const isVideo = !!result.videoUrl;

  const CONFIDENCE_BADGE_STYLE = {
    HIGH:   'bg-fintech-soft text-fintech-green border-fintech-green/20',
    MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
    LOW:    'bg-slate-100 text-slate-600 border-slate-200',
  };

  return (
    <div className={`rounded-xl border ${theme.border} ${theme.bg} p-8 shadow-md my-6 transition-all duration-500`}>

      <div className="mb-6">
        <h2 className="text-xs font-bold text-fintech-secondary tracking-widest uppercase mb-1">Forensic Case</h2>
      </div>

      {/* Forensic Video / Image Player */}
      {mediaUrl && (
        <ForensicVideoPlayer mediaUrl={mediaUrl} result={result} isVideo={isVideo} />
      )}

      {/* Top Banner */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-fintech-border pb-6 mt-6">
        <div className="flex items-center space-x-4">
          <div className={`p-4 rounded-xl border border-black/5 ${theme.iconColor}`}>
            <HeaderIcon className="w-8 h-8" />
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-fintech-text tracking-tight mb-2">{theme.title}</h2>
            <div className="flex items-center flex-wrap gap-2">
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider border ${CONFIDENCE_BADGE_STYLE[confidence] || CONFIDENCE_BADGE_STYLE.MEDIUM}`}>
                AI Confidence: {confidence}
              </span>
            </div>
          </div>
        </div>
        <div className="text-right">
          <span className="text-[10px] uppercase font-bold tracking-widest text-fintech-secondary block mb-1">Flag ID</span>
          <span className="text-base font-mono text-fintech-text bg-slate-50 px-3 py-1 rounded border border-slate-200">FS-{result.id.substring(0,6)}</span>
        </div>
      </div>

      {/* Summary */}
      <div className="mt-6">
         <h3 className="text-xs font-bold uppercase tracking-wider text-fintech-secondary mb-2">Executive Summary</h3>
         <p className="text-fintech-text text-sm font-medium leading-relaxed max-w-4xl">
           {result.summary}
         </p>
      </div>

      {/* Dual Axis Score Gauge */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">

        {/* Axis 1: Visual Deepfake */}
        <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-fintech-secondary flex items-center">
              <Cpu className="w-4 h-4 mr-2" /> Visual Forensics
            </span>
          </div>
          <div className="flex justify-between items-end mb-2">
            <span className="text-sm font-semibold text-fintech-text">Deepfake Score</span>
            <span className="font-mono font-bold text-xl text-fintech-text">{(result.deepfake_score * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full h-2 bg-slate-200 rounded-sm overflow-hidden mb-4">
            <div
              className={`h-full transition-all duration-1000 ${result.is_deepfake ? 'bg-fintech-red' : 'bg-fintech-green'}`}
              style={{ width: `${Math.max(5, result.deepfake_score * 100)}%` }}
            />
          </div>
          <p className="text-xs text-fintech-secondary font-medium leading-relaxed">{result.visual_summary}</p>
          
          {/* New Visual Forensics Display */}
          {(result.watermark_detected && result.watermark_detected !== "none" || result.gemini_reasoning || (result.artifacts && result.artifacts.length > 0)) && (
            <div className="mt-4 pt-4 border-t border-slate-200">
              <span className="text-xs font-bold text-fintech-text block mb-2">Why this score?</span>
              {result.watermark_detected && result.watermark_detected !== "none" && (
                <div className="flex items-center gap-2 mb-2 text-sm text-fintech-secondary">
                  <span className="text-fintech-action">→</span> AI Watermark detected ({result.watermark_detected})
                </div>
              )}
              {result.artifacts && result.artifacts.length > 0 && (
                <div className="mb-2">
                   <ul className="space-y-1">
                     {result.artifacts.map((art, idx) => (
                        <li key={idx} className="text-sm text-fintech-secondary flex items-start gap-2">
                          <span className="text-fintech-action">→</span> {art}
                        </li>
                     ))}
                   </ul>
                </div>
              )}
              {result.gemini_reasoning && (
                <div className="mt-3 bg-white p-3 rounded shadow-sm border border-slate-200">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-fintech-secondary block mb-1">AI Reasoning Analysis</span>
                  <p className="text-xs text-fintech-text leading-relaxed">"{result.gemini_reasoning}"</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Axis 2: SEBI Compliance */}
        <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-fintech-secondary flex items-center">
              <Scale className="w-4 h-4 mr-2" /> SEBI Compliance
            </span>
          </div>
          <div className="flex justify-between items-end mb-2">
            <span className="text-sm font-semibold text-fintech-text">SEBI Risk Score</span>
            <span className="font-mono font-bold text-xl text-fintech-text">{(result.sebi_risk_score * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full h-2 bg-slate-200 rounded-sm overflow-hidden mb-4">
            <div
              className={`h-full transition-all duration-1000 ${result.is_sebi_violation ? 'bg-fintech-red' : 'bg-fintech-green'}`}
              style={{ width: `${Math.max(5, result.sebi_risk_score * 100)}%` }}
            />
          </div>
          <p className="text-xs text-fintech-secondary font-medium leading-relaxed">{result.sebi_summary}</p>
        </div>

      </div>

      {/* Audio Transcript */}
      {result.transcript && (
        <div className="mt-8">
          <span className="text-xs font-bold uppercase tracking-wider text-fintech-secondary block mb-3">
            Extracted Transcript
          </span>
          <div className="bg-white border border-fintech-border rounded-xl p-5 shadow-sm">
             <p className="text-sm font-mono text-fintech-text leading-relaxed">
               "{result.transcript}"
             </p>
          </div>
        </div>
      )}

      {/* Forensic Evidence & SEBI Citations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-8 border-t border-fintech-border pt-8">

        {/* Reasons */}
        <div>
          <span className="text-xs font-bold uppercase text-fintech-secondary block mb-4 flex items-center tracking-widest">
            Regulatory Violations
          </span>
          <ul className="space-y-3">
            {(result.reasons || []).map((reason, i) => {
              const isCompliant = reason.startsWith('[COMPLIANT]');
              return (
                <li key={i} className={`text-sm flex items-start gap-3 ${isCompliant ? 'text-fintech-green' : 'text-fintech-text'}`}>
                  <span className={`mt-0.5 font-bold ${isCompliant ? 'text-fintech-green' : 'text-fintech-red'}`}>
                    {isCompliant ? '✓' : '×'}
                  </span>
                  <span className="leading-snug">{reason.replace(/^\[(SIGNAL|COMPLIANT)\]\s*/, '')}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* SEBI Rules */}
        <div>
          <span className="text-xs font-bold uppercase text-fintech-secondary block mb-4 flex items-center tracking-widest">
            Regulatory Citations
          </span>
          <ul className="space-y-3">
            {(result.sebi_rules || []).map((rule, i) => (
              <li key={i} className="text-sm text-fintech-text flex items-start gap-3">
                <span className="text-fintech-action mt-0.5">⚖</span>
                <span className="leading-snug">{rule}</span>
              </li>
            ))}
          </ul>
        </div>

      </div>

      {/* Case Metadata Strip */}
      <div className="mt-8 flex flex-wrap gap-6 p-4 bg-fintech-bg rounded-lg border border-fintech-border text-xs font-mono text-fintech-secondary items-center uppercase tracking-widest">
         <div>Flag ID: <span className="font-bold text-fintech-text">FS-{result.id.substring(0,8)}</span></div>
         <div>Media Type: <span className="font-bold text-fintech-text">{result.media_type}</span></div>
         <div>Threat Level: <span className="font-bold text-fintech-text">{result.dual_verdict.includes('VIOLATION') ? 'HIGH' : 'SAFE'}</span></div>
         <div>AI Confidence: <span className="font-bold text-fintech-text">{confidence}</span></div>
      </div>

    </div>
  );
}
