import React from 'react';
import { AlertOctagon, CheckCircle2, Cpu, AlertTriangle, ShieldCheck, FileText, Scale, Activity, Bug, BadgeCheck, Info } from 'lucide-react';

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
          bg: 'bg-red-950/40', border: 'border-red-500/50',
          badgeBg: 'bg-red-500/20 text-red-400 border-red-500/30',
          icon: AlertOctagon, iconColor: 'text-red-400',
          title: '🚨 HIGH RISK SCAM DETECTED'
        };
      case 'AI_SEBI_COMPLIANT':
        return {
          bg: 'bg-blue-950/40', border: 'border-blue-500/50',
          badgeBg: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
          icon: Cpu, iconColor: 'text-blue-400',
          title: '🟦 AI MEDIA DETECTED (SEBI COMPLIANT)'
        };
      case 'REAL_SEBI_VIOLATION':
        return {
          bg: 'bg-amber-950/40', border: 'border-amber-500/50',
          badgeBg: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
          icon: AlertTriangle, iconColor: 'text-amber-400',
          title: '🟧 SEBI REGULATORY VIOLATION'
        };
      default:
        return {
          bg: 'bg-emerald-950/40', border: 'border-emerald-500/50',
          badgeBg: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
          icon: ShieldCheck, iconColor: 'text-emerald-400',
          title: '🟩 SAFE & SEBI VERIFIED'
        };
    }
  };

  const theme = getVerdictTheme();
  const HeaderIcon = theme.icon;
  const schemes = (result.detected_schemes || []).filter(s => s !== 'none');
  const complianceSignals = result.compliance_signals || [];
  const confidence = result.confidence || 'MEDIUM';

  return (
    <div className={`rounded-2xl border ${theme.border} ${theme.bg} p-6 glass-panel shadow-2xl my-6`}>

      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="flex items-center space-x-3">
          <div className={`p-3 rounded-2xl bg-slate-900/90 border border-slate-800 ${theme.iconColor}`}>
            <HeaderIcon className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center flex-wrap gap-2">
              <span className={`text-xs font-bold px-3 py-1 rounded-full uppercase border ${theme.badgeBg}`}>
                {result.dual_verdict.replace(/_/g, ' ')}
              </span>
              {/* AI Confidence Badge */}
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border ${CONFIDENCE_BADGE[confidence] || CONFIDENCE_BADGE.MEDIUM}`}>
                AI Confidence: {confidence}
              </span>
              <span className="text-xs text-slate-500 font-mono">#{result.id}</span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1">{theme.title}</h2>
          </div>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-400 block font-medium">Evaluation Timestamp</span>
          <span className="text-xs font-mono text-slate-300">{new Date(result.timestamp).toLocaleString()}</span>
        </div>
      </div>

      {/* Summary */}
      <div className="mt-4 bg-slate-900/70 rounded-xl p-4 border border-slate-800 text-slate-200 text-sm font-medium leading-relaxed">
        {result.summary}
      </div>

      {/* Detected Scheme Types */}
      {schemes.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center">
            <Bug className="w-3.5 h-3.5 mr-1.5 text-red-400" /> Detected Schemes:
          </span>
          {schemes.map(s => {
            const info = SCHEME_LABEL[s];
            if (!info) return null;
            return (
              <span key={s} className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${info.color}`}>
                {info.label}
              </span>
            );
          })}
        </div>
      )}

      {/* Dual Axis Score Gauge */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">

        {/* Axis 1: Visual Deepfake */}
        <div className="glass-card p-4 rounded-xl border border-slate-800/80 bg-slate-900/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center">
              <Cpu className="w-4 h-4 mr-1.5 text-purple-400" /> Axis 1: Visual Authenticity
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result.is_deepfake ? 'bg-purple-500/20 text-purple-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
              {result.is_deepfake ? 'AI DEEPFAKE' : 'AUTHENTIC'}
            </span>
          </div>
          <div className="flex justify-between text-xs text-slate-400 mb-1 font-medium">
            <span>Deepfake Score</span>
            <span className="font-bold text-white">{(result.deepfake_score * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-1000 ${result.is_deepfake ? 'bg-gradient-to-r from-purple-500 to-pink-500' : 'bg-emerald-500'}`}
              style={{ width: `${Math.max(5, result.deepfake_score * 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2 font-medium">{result.visual_summary}</p>
        </div>

        {/* Axis 2: SEBI Compliance */}
        <div className="glass-card p-4 rounded-xl border border-slate-800/80 bg-slate-900/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center">
              <Scale className="w-4 h-4 mr-1.5 text-amber-400" /> Axis 2: SEBI Spoken Compliance
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result.is_sebi_violation ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
              {result.is_sebi_violation ? 'SEBI VIOLATION' : 'SEBI COMPLIANT'}
            </span>
          </div>
          <div className="flex justify-between text-xs text-slate-400 mb-1 font-medium">
            <span>SEBI Risk Score</span>
            <span className="font-bold text-white">{(result.sebi_risk_score * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-1000 ${result.is_sebi_violation ? 'bg-gradient-to-r from-amber-500 to-red-500' : 'bg-emerald-500'}`}
              style={{ width: `${Math.max(5, result.sebi_risk_score * 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2 font-medium">{result.sebi_summary}</p>
        </div>

      </div>

      {/* Audio Transcript */}
      {result.transcript && result.media_type !== 'text' && (
        <div className="mt-6 bg-slate-950/80 rounded-xl p-4 border border-slate-800">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center mb-2">
            <FileText className="w-4 h-4 mr-1.5 text-blue-400" /> Extracted Audio Speech Transcript
          </span>
          <p className="text-xs font-mono text-slate-300 bg-slate-900 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
            "{result.transcript}"
          </p>
        </div>
      )}

      {/* For text scans, show the analyzed text */}
      {result.media_type === 'text' && result.transcript && (
        <div className="mt-6 bg-slate-950/80 rounded-xl p-4 border border-slate-800">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center mb-2">
            <Activity className="w-4 h-4 mr-1.5 text-blue-400" /> Analyzed Investment Communication
          </span>
          <p className="text-xs font-mono text-slate-300 bg-slate-900 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
            "{result.transcript}"
          </p>
        </div>
      )}

      {/* Forensic Evidence & SEBI Citations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">

        {/* Reasons */}
        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs font-bold uppercase text-slate-400 block mb-3 flex items-center">
            <AlertOctagon className="w-3.5 h-3.5 mr-1.5 text-red-400" /> Forensic Findings
          </span>
          <ul className="space-y-2">
            {(result.reasons || []).map((reason, i) => {
              const isCompliant = reason.startsWith('[COMPLIANT]');
              return (
                <li key={i} className={`text-xs flex items-start gap-2 ${isCompliant ? 'text-emerald-400' : 'text-slate-300'}`}>
                  <span className={`mt-0.5 flex-shrink-0 ${isCompliant ? 'text-emerald-400' : 'text-red-400'}`}>
                    {isCompliant ? '✓' : '✗'}
                  </span>
                  <span>{reason.replace(/^\[(SIGNAL|COMPLIANT)\]\s*/, '')}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* SEBI Rules */}
        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs font-bold uppercase text-slate-400 block mb-3 flex items-center">
            <Scale className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> SEBI Regulatory Citations
          </span>
          <ul className="space-y-2">
            {(result.sebi_rules || []).map((rule, i) => (
              <li key={i} className="text-xs text-blue-300 flex items-start gap-2">
                <span className="flex-shrink-0 text-blue-500 mt-0.5">⚖️</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>

          {/* Compliance Signals (positive markers) */}
          {complianceSignals.length > 0 && complianceSignals[0] !== 'none' && (
            <div className="mt-4 pt-3 border-t border-slate-800">
              <span className="text-[10px] font-bold uppercase text-emerald-400 block mb-2 flex items-center gap-1">
                <BadgeCheck className="w-3 h-3" /> Compliance Markers Found
              </span>
              <ul className="space-y-1">
                {complianceSignals.map((s, i) => (
                  <li key={i} className="text-[11px] text-emerald-300 flex items-start gap-1">
                    <span>✓</span><span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

      </div>

      {/* Info Footer */}
      <div className="mt-5 flex items-start gap-2 p-3 bg-slate-900/40 rounded-xl border border-slate-800/60 text-xs text-slate-500 font-medium">
        <Info className="w-4 h-4 flex-shrink-0 mt-0.5 text-blue-500/60" />
        <span>
          This forensic verdict was generated by a 3-layer SEBI compliance engine: structural pattern scan (24 weighted signals),
          Gemini Pro deep chain-of-thought analysis with ensemble blending, and SEBI enforcement regulation citations.
          Threshold: {'>'}60% risk score triggers SEBI Violation verdict.
        </span>
      </div>

    </div>
  );
}
