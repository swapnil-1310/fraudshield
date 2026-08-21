import React from 'react';
import { AlertTriangle, Trash2, Eye, ShieldAlert, Cpu, Scale } from 'lucide-react';

export default function RegulatorLiveFeed({ reports = [], onSelectReport, onDeleteReport }) {
  if (!reports || reports.length === 0) {
    return (
      <div className="glass-panel p-8 rounded-2xl text-center border border-slate-800 my-6">
        <ShieldAlert className="w-12 h-12 text-slate-500 mx-auto mb-3" />
        <h3 className="text-lg font-bold text-white">No Flagged Reports Yet</h3>
        <p className="text-xs text-slate-400 mt-1">Run a media scan or text tip analysis to generate SEBI audit reports.</p>
      </div>
    );
  }

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case 'AI_SEBI_VIOLATION':
        return <span className="bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] font-extrabold px-2.5 py-1 rounded-full uppercase">🚨 High Risk Scam</span>;
      case 'AI_SEBI_COMPLIANT':
        return <span className="bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] font-extrabold px-2.5 py-1 rounded-full uppercase">🟦 AI Legit</span>;
      case 'REAL_SEBI_VIOLATION':
        return <span className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] font-extrabold px-2.5 py-1 rounded-full uppercase">🟧 SEBI Violation</span>;
      default:
        return <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-extrabold px-2.5 py-1 rounded-full uppercase">🟩 Safe</span>;
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-slate-800 p-6 my-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center">
            <ShieldAlert className="w-5 h-5 mr-2 text-blue-400" /> Real-time SEBI Regulatory Live Audit Feed
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 font-medium">Live monitoring queue for investor fraud cases and deepfake alerts</p>
        </div>
        <span className="bg-blue-500/10 text-blue-400 text-xs font-bold px-3 py-1 rounded-full border border-blue-500/20">
          {reports.length} Total Reports
        </span>
      </div>

      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {reports.map((report) => (
          <div
            key={report.id}
            className="glass-card p-4 rounded-xl border border-slate-800/80 bg-slate-900/60 hover:border-slate-700 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
          >
            <div className="flex items-start space-x-3">
              <div className="p-2.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 mt-0.5">
                {report.media_type === 'video' ? <Cpu className="w-5 h-5 text-purple-400" /> : <Scale className="w-5 h-5 text-amber-400" />}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs text-slate-400 font-bold">{report.id}</span>
                  {getVerdictBadge(report.dual_verdict)}
                </div>
                <h4 className="text-sm font-bold text-white mt-1">{report.title}</h4>
                <p className="text-xs text-slate-400 mt-0.5 line-clamp-1 font-medium">{report.summary}</p>
                <div className="flex items-center space-x-4 mt-2 text-[11px] text-slate-500 font-mono">
                  <span>Deepfake: {(report.deepfake_score * 100).toFixed(0)}%</span>
                  <span>SEBI Risk: {(report.sebi_risk_score * 100).toFixed(0)}%</span>
                  <span>{new Date(report.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2 self-end md:self-center">
              <button
                onClick={() => onSelectReport(report)}
                className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white border border-blue-500/30 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer"
              >
                <Eye className="w-3.5 h-3.5" />
                <span>View Card</span>
              </button>
              <button
                onClick={() => onDeleteReport(report.id)}
                className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
                title="Dismiss flag"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
