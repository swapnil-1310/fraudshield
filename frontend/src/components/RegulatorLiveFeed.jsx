import React from 'react';
import { AlertTriangle, Trash2, Eye, ShieldAlert, Cpu, Scale } from 'lucide-react';

export default function RegulatorLiveFeed({ reports = [], onSelectReport, onDeleteReport }) {
  if (!reports || reports.length === 0) {
    return (
      <div className="fintech-card p-12 text-center my-6 border-dashed border-2 border-fintech-border bg-slate-50">
        <div className="bg-white p-4 rounded-full inline-block mb-4 shadow-sm">
          <ShieldAlert className="w-8 h-8 text-fintech-secondary" />
        </div>
        <h3 className="text-lg font-bold text-fintech-text uppercase tracking-widest">No Flags Detected</h3>
        <p className="text-sm text-fintech-secondary mt-2">Run a scan or analysis to generate regulatory audit reports.</p>
      </div>
    );
  }

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case 'AI_SEBI_VIOLATION':
        return <span className="bg-red-50 text-fintech-red border border-red-200 text-[10px] font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">High Risk Scam</span>;
      case 'AI_SEBI_COMPLIANT':
        return <span className="bg-blue-50 text-fintech-blue border border-blue-200 text-[10px] font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">AI Legit</span>;
      case 'REAL_SEBI_VIOLATION':
        return <span className="bg-amber-50 text-fintech-amber border border-amber-200 text-[10px] font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">SEBI Violation</span>;
      default:
        return <span className="bg-fintech-soft text-fintech-green border border-fintech-green/20 text-[10px] font-bold px-2.5 py-1 rounded-sm uppercase tracking-wider">Safe</span>;
    }
  };

  return (
    <div className="fintech-card p-8 my-6">
      <div className="flex items-center justify-between border-b border-fintech-border pb-6 mb-6">
        <div>
          <h2 className="text-xl font-bold text-fintech-text flex items-center tracking-tight">
            <ShieldAlert className="w-5 h-5 mr-3 text-fintech-action" /> Regulatory Audit Queue
          </h2>
          <p className="text-sm text-fintech-secondary mt-1 font-medium">Real-time monitoring queue for forensic cases</p>
        </div>
        <span className="bg-slate-100 text-fintech-secondary text-xs font-bold px-3 py-1.5 rounded-sm border border-slate-200 uppercase tracking-widest">
          {reports.length} Reports
        </span>
      </div>

      <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
        {reports.map((report) => (
          <div
            key={report.id}
            className="bg-white p-5 rounded-xl border border-fintech-border hover:border-fintech-green/50 hover:shadow-md transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 group"
          >
            <div className="flex items-start space-x-4">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-fintech-secondary group-hover:text-fintech-action transition-colors">
                {report.media_type === 'video' ? <Cpu className="w-5 h-5" /> : <Scale className="w-5 h-5" />}
              </div>
              <div>
                <div className="flex items-center space-x-3 mb-1">
                  <span className="font-mono text-xs font-bold text-fintech-secondary uppercase tracking-widest bg-slate-50 px-2 py-0.5 rounded border border-slate-200">FS-{report.id.substring(0,6)}</span>
                  {getVerdictBadge(report.dual_verdict)}
                </div>
                <h4 className="text-sm font-bold text-fintech-text mt-1.5">{report.title}</h4>
                <p className="text-xs text-fintech-secondary mt-1 line-clamp-1 font-medium">{report.summary}</p>
                
                <div className="flex items-center space-x-6 mt-3 text-[11px] font-mono font-medium text-slate-500 uppercase tracking-wider">
                  <div>Visual: <span className="text-fintech-text font-bold">{(report.deepfake_score * 100).toFixed(0)}%</span></div>
                  <div>SEBI: <span className="text-fintech-text font-bold">{(report.sebi_risk_score * 100).toFixed(0)}%</span></div>
                  <div className="text-slate-400">{new Date(report.timestamp).toLocaleTimeString()}</div>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-3 self-end md:self-center">
              <button
                onClick={() => onSelectReport(report)}
                className="px-4 py-2 bg-fintech-verysoft hover:bg-fintech-soft text-fintech-green border border-fintech-green/30 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center space-x-2 transition-colors cursor-pointer"
              >
                <Eye className="w-4 h-4" />
                <span>View Case</span>
              </button>
              <button
                onClick={() => onDeleteReport(report.id)}
                className="p-2 text-slate-400 hover:text-fintech-red hover:bg-red-50 rounded-lg transition-colors cursor-pointer border border-transparent hover:border-red-100"
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
