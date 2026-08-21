import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import KPICards from './components/KPICards';
import MediaUploadModal from './components/MediaUploadModal';
import DualVerdictCard from './components/DualVerdictCard';
import RegulatorLiveFeed from './components/RegulatorLiveFeed';
import AdvisorVerifier from './components/AdvisorVerifier';
import ScreenshotUploadModal from './components/ScreenshotUploadModal';

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
    <div className="min-h-screen bg-fintech-bg text-fintech-text selection:bg-fintech-action selection:text-white pb-20 font-sans">
      
      {/* Header Navbar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="max-w-5xl mx-auto px-4 lg:px-8 pt-8">
        
        {/* Main Hero (Only on Scanners) */}
        {(activeTab === 'scanner' || activeTab === 'app_scanner') && (
          <div className="text-center mb-10 mt-6">
            <h1 className="text-4xl md:text-5xl font-extrabold text-fintech-text tracking-tight mb-4">
              Detect. Verify. Protect.
            </h1>
            <p className="text-lg text-fintech-secondary font-medium max-w-2xl mx-auto">
              AI-powered visual, audio and regulatory analysis for suspicious financial content.
            </p>
          </div>
        )}

        {/* Tab 1: Dual Media Scanner & Verification */}
        {activeTab === 'scanner' && (
          <div className="space-y-8">
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

        {/* Tab 1.5: Screenshot Scanner */}
        {activeTab === 'app_scanner' && (
          <div className="space-y-6">
            <ScreenshotUploadModal onScanComplete={handleScanComplete} />

            {/* Display Latest Dual Verdict Card */}
            {latestScan && (
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Forensic Visual Result Card
                </h3>
                <DualVerdictCard result={latestScan} />
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Regulator Dashboard */}
        {activeTab === 'regulator' && (
          <div className="max-w-7xl mx-auto">
            <div className="mb-8">
              <h2 className="text-3xl font-bold text-fintech-text mb-2">Regulator Dashboard</h2>
              <p className="text-fintech-secondary font-medium">Monitor analyzed cases, fraud signals and regulatory risk.</p>
            </div>
            
            {/* KPI Metric Cards moved to dashboard */}
            <div className="mb-8">
               <KPICards stats={stats} />
            </div>
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
      <footer className="max-w-5xl mx-auto px-4 lg:px-8 mt-16 pt-8 border-t border-fintech-border text-center text-xs text-fintech-secondary font-medium">
        FraudShield SEBI Pro • Premium Financial Compliance Intelligence Platform
      </footer>

    </div>
  );
}
