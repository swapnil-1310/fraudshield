import React from 'react';
import { ShieldCheck, Eye, AlertTriangle, Cpu, TrendingUp } from 'lucide-react';

export default function KPICards({ stats = {} }) {
  const cards = [
    {
      title: 'Total Scans Evaluated',
      value: stats.total_scans ?? 0,
      subtext: 'Real-time media & text tips',
      icon: Eye,
      color: 'from-blue-500/20 to-indigo-500/10',
      borderColor: 'border-blue-500/30',
      iconColor: 'text-blue-400'
    },
    {
      title: 'Deepfake Media Flagged',
      value: stats.total_deepfakes ?? 0,
      subtext: 'Visual AI manipulation detected',
      icon: Cpu,
      color: 'from-purple-500/20 to-pink-500/10',
      borderColor: 'border-purple-500/30',
      iconColor: 'text-purple-400'
    },
    {
      title: 'SEBI Spoken Violations',
      value: stats.total_sebi_violations ?? 0,
      subtext: 'Guaranteed returns & unregistered advice',
      icon: AlertTriangle,
      color: 'from-amber-500/20 to-orange-500/10',
      borderColor: 'border-amber-500/30',
      iconColor: 'text-amber-400'
    },
    {
      title: 'High Risk AI Scams',
      value: stats.total_high_risk_scams ?? 0,
      subtext: 'AI Deepfake + SEBI Violation Matrix',
      icon: ShieldCheck,
      color: 'from-red-500/20 to-rose-500/10',
      borderColor: 'border-red-500/30',
      iconColor: 'text-red-400'
    }
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {cards.map((card, idx) => {
        const IconComponent = card.icon;
        return (
          <div
            key={idx}
            className={`glass-card p-5 rounded-2xl border ${card.borderColor} bg-gradient-to-br ${card.color} relative overflow-hidden transition-all hover:scale-[1.02]`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                {card.title}
              </span>
              <div className={`p-2 rounded-xl bg-slate-900/80 border border-slate-800 ${card.iconColor}`}>
                <IconComponent className="w-5 h-5" />
              </div>
            </div>

            <div className="mt-4 flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-white tracking-tight">
                {card.value}
              </span>
              <span className="flex items-center text-xs font-medium text-emerald-400">
                <TrendingUp className="w-3.5 h-3.5 mr-1" /> Live
              </span>
            </div>

            <p className="mt-2 text-xs text-slate-400 font-medium">
              {card.subtext}
            </p>
          </div>
        );
      })}
    </div>
  );
}
