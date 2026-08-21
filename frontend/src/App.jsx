import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import KPICards from './components/KPICards';
import MediaUploadModal from './components/MediaUploadModal';
import DualVerdictCard from './components/DualVerdictCard';
import RegulatorLiveFeed from './components/RegulatorLiveFeed';
import AdvisorVerifier from './components/AdvisorVerifier';

export default function App() {
  const [activeTab, setActiveTab] = useState('scanner'); // 'scanner' | 'regulator' | 'advisor'
  const [latestScan, setLatestScan] = useState(null);
  const [reports, setReports] = useState([]);
  const [stats, setStats] = useState({ total_scans: 0, total_deepfakes: 0, total_sebi_violations: 0, total_high_risk_scams: 0 });

  const fetchReportsAndStats = async () => {
    try {
      const [resFlags, resStats] = await Promise.all([
        fetch('http://127.0.0.1:8000/api/flags'),
        fetch('http://127.0.0.1:8000/api/stats')
      ]);

      if (resFlags.ok) {
        const flagsData = await resFlags.json();
        setReports(flagsData);
      }
      if (resStats.ok) {
        const statsData = await resStats.json();
        setStats(statsData);
      }
    } catch (err) {
      console.log('Backend sync note: ensure uvicorn API server is active on port 8000.');
    }
  };

  useEffect(() => {
    fetchReportsAndStats();
  }, []);

  const handleScanComplete = (resultData) => {
    setLatestScan(resultData);
    fetchReportsAndStats();
  };

  const handleDeleteReport = async (reportId) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/flags/${reportId}`, { method: 'DELETE' });
      if (latestScan && latestScan.id === reportId) {
        setLatestScan(null);
      }
      fetchReportsAndStats();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-[#050914] text-slate-100 selection:bg-blue-600 selection:text-white pb-20">
      
      {/* Header Navbar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="max-w-7xl mx-auto px-4 lg:px-8 pt-8">
        
        {/* KPI Metric Cards */}
        <KPICards stats={stats} />

        {/* Tab 1: Dual Media Scanner & Verification */}
        {activeTab === 'scanner' && (
          <div className="space-y-6">
            <MediaUploadModal onScanComplete={handleScanComplete} />

            {/* Display Latest Dual Verdict Card */}
            {latestScan && (
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Dual Matrix Audit Result Card
                </h3>
                <DualVerdictCard result={latestScan} />
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Regulator Dashboard */}
        {activeTab === 'regulator' && (
          <div>
            {latestScan && (
              <div className="mb-6">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Active Selected Audit Report
                </h3>
                <DualVerdictCard result={latestScan} />
              </div>
            )}
            <RegulatorLiveFeed
              reports={reports}
              onSelectReport={(report) => setLatestScan(report)}
              onDeleteReport={handleDeleteReport}
            />
          </div>
        )}

        {/* Tab 3: SEBI Advisor Verification */}
        {activeTab === 'advisor' && (
          <div>
            <AdvisorVerifier />
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-4 lg:px-8 mt-16 pt-8 border-t border-slate-800 text-center text-xs text-slate-500 font-medium">
        FraudShield-SEBI Pro • AI Deepfake Media & SEBI Compliance Detection Platform • Aligned with SEBI Investor Protection Mandate
      </footer>

    </div>
  );
}
