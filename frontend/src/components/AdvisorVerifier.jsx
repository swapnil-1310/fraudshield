import React, { useState } from 'react';
import { Search, ShieldCheck, ShieldAlert, AlertTriangle, Building, CheckCircle2 } from 'lucide-react';

export default function AdvisorVerifier() {
  const [regNo, setRegNo] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!regNo.trim()) return;
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/verify-advisor/${encodeURIComponent(regNo.trim())}`);
      if (!res.ok) throw new Error('Could not fetch advisor details');
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setError('Advisor verification request failed. Ensure backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 my-6">
      <div className="border-b border-slate-800 pb-4 mb-6">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center">
          <Search className="w-5 h-5 mr-2 text-blue-400" /> SEBI Registered Advisor Verification Portal
        </h2>
        <p className="text-xs text-slate-400 mt-1 font-medium">
          Cross-check Research Analyst (RA) and Investment Adviser (RIA) registration IDs against the official SEBI database
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          value={regNo}
          onChange={(e) => setRegNo(e.target.value)}
          placeholder="Enter Registration ID (e.g. INH000005678 or INA000001234)..."
          className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl shadow-lg shadow-blue-500/20 flex items-center justify-center space-x-2 transition-all cursor-pointer"
        >
          {loading ? <span>Verifying...</span> : <span>Search Database</span>}
        </button>
      </form>

      {/* Quick Test Chips */}
      <div className="flex flex-wrap items-center gap-2 mb-6 text-xs text-slate-400">
        <span className="font-semibold">Try sample IDs:</span>
        <button onClick={() => setRegNo('INH000005678')} className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-mono">INH000005678 (Valid RA)</button>
        <button onClick={() => setRegNo('INA000001234')} className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-mono">INA000001234 (Valid RIA)</button>
        <button onClick={() => setRegNo('INA000004321')} className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-mono">INA000004321 (Suspended)</button>
        <button onClick={() => setRegNo('FAKE99999')} className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 font-mono">FAKE99999 (Unregistered)</button>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl text-xs font-semibold">
          {error}
        </div>
      )}

      {/* Verification Card Result */}
      {result && (
        <div className={`p-6 rounded-2xl border ${result.is_valid ? 'bg-emerald-950/30 border-emerald-500/40' : 'bg-red-950/30 border-red-500/40'} glass-card`}>
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
            <div className="flex items-center space-x-3">
              <div className={`p-3 rounded-xl ${result.is_valid ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                {result.is_valid ? <ShieldCheck className="w-8 h-8" /> : <ShieldAlert className="w-8 h-8" />}
              </div>
              <div>
                <span className="font-mono text-xs text-slate-400">REGISTRATION ID: {result.reg_no}</span>
                <h3 className="text-xl font-bold text-white mt-0.5">{result.name || 'Unregistered Entity'}</h3>
              </div>
            </div>

            <span className={`text-xs font-extrabold uppercase px-3 py-1 rounded-full border ${
              result.status === 'VALID' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'
            }`}>
              STATUS: {result.status}
            </span>
          </div>

          <p className="text-sm font-medium text-slate-300 mb-4">{result.details}</p>

          {result.is_valid && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs bg-slate-900/80 p-4 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-400 block font-medium">Category</span>
                <span className="font-bold text-white">{result.category}</span>
              </div>
              <div>
                <span className="text-slate-400 block font-medium">Associated Company</span>
                <span className="font-bold text-white">{result.company}</span>
              </div>
              <div>
                <span className="text-slate-400 block font-medium">Registration Validity</span>
                <span className="font-bold text-white">{result.valid_till}</span>
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
}
