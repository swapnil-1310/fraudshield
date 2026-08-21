import React from 'react';
import { Shield, ShieldAlert, LayoutDashboard, Search, FileText, Image as ImageIcon } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab }) {
  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-fintech-border px-4 lg:px-8 py-4 shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('scanner')}>
          <div className="w-10 h-10 rounded-lg bg-fintech-green flex items-center justify-center shadow-md">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-xl tracking-tight text-fintech-text">FraudShield</span>
              <span className="bg-fintech-soft text-fintech-green border border-fintech-green/20 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                SEBI Pro
              </span>
            </div>
            <p className="text-xs text-fintech-secondary font-medium">Dual Visual & Audio SEBI Compliance Platform</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="hidden md:flex items-center space-x-6">
          <button
            onClick={() => setActiveTab('scanner')}
            className={`flex items-center space-x-2 pb-1 border-b-2 text-sm font-semibold transition-all ${
              activeTab === 'scanner'
                ? 'border-fintech-green text-fintech-green'
                : 'border-transparent text-fintech-secondary hover:text-fintech-text'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Dual Scanner</span>
          </button>

          <button
            onClick={() => setActiveTab('app_scanner')}
            className={`flex items-center space-x-2 pb-1 border-b-2 text-sm font-semibold transition-all ${
              activeTab === 'app_scanner'
                ? 'border-fintech-green text-fintech-green'
                : 'border-transparent text-fintech-secondary hover:text-fintech-text'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>App Scanner</span>
          </button>

          <button
            onClick={() => setActiveTab('regulator')}
            className={`flex items-center space-x-2 pb-1 border-b-2 text-sm font-semibold transition-all ${
              activeTab === 'regulator'
                ? 'border-fintech-green text-fintech-green'
                : 'border-transparent text-fintech-secondary hover:text-fintech-text'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Regulator Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('advisor')}
            className={`flex items-center space-x-2 pb-1 border-b-2 text-sm font-semibold transition-all ${
              activeTab === 'advisor'
                ? 'border-fintech-green text-fintech-green'
                : 'border-transparent text-fintech-secondary hover:text-fintech-text'
            }`}
          >
            <Search className="w-4 h-4" />
            <span>SEBI Advisor Lookup</span>
          </button>
        </div>

        {/* Status Badge */}
        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 text-fintech-green px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide">
            <span className="w-2 h-2 rounded-full bg-fintech-action animate-pulse"></span>
            <span>SEBI REGULATIONS 2026 ENGINE ACTIVE</span>
          </div>
        </div>

      </div>
    </nav>
  );
}
