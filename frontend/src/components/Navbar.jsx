import React from 'react';
import { Shield, ShieldAlert, LayoutDashboard, Search, FileText } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab }) {
  return (
    <nav className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-4 lg:px-8 py-3.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('scanner')}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-blue-500/20">
            <div className="w-full h-full bg-[#0A1224] rounded-[10px] flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-lg tracking-tight text-white">FraudShield</span>
              <span className="bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                SEBI Pro
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">Dual Visual & Audio SEBI Compliance Platform</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="hidden md:flex items-center space-x-1 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('scanner')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'scanner'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Dual Scanner</span>
          </button>

          <button
            onClick={() => setActiveTab('regulator')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'regulator'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Regulator Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('advisor')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'advisor'
                ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Search className="w-4 h-4" />
            <span>SEBI Advisor Lookup</span>
          </button>
        </div>

        {/* Status Badge */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-3 py-1.5 rounded-lg text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>SEBI Regulations 2024 Engine Active</span>
          </div>
        </div>

      </div>
    </nav>
  );
}
