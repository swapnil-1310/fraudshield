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
    <div className="fintech-card p-8 my-6">
      <div className="border-b border-fintech-border pb-6 mb-6">
        <h2 className="text-xl font-bold text-fintech-text tracking-tight flex items-center">
          <Search className="w-5 h-5 mr-3 text-fintech-action" /> Regulatory Entity Verification Portal
        </h2>
        <p className="text-sm text-fintech-secondary mt-1 font-medium">
          Cross-check Research Analyst (RA) and Investment Adviser (RIA) credentials against the official SEBI database
        </p>
      </div>

      <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4 mb-8">
        <input
          type="text"
          value={regNo}
          onChange={(e) => setRegNo(e.target.value)}
          placeholder="Enter Registration ID (e.g. INH000005678)..."
          className="flex-1 bg-fintech-verysoft border border-fintech-border rounded-xl px-4 py-4 text-base text-fintech-text focus:outline-none focus:border-fintech-green focus:ring-1 focus:ring-fintech-green font-mono shadow-inner"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-8 py-4 bg-fintech-action hover:bg-fintech-dark text-white font-bold rounded-xl shadow-[0_4px_14px_0_rgba(22,160,93,0.39)] hover:shadow-[0_6px_20px_rgba(22,160,93,0.23)] hover:-translate-y-0.5 flex items-center justify-center space-x-2 transition-all cursor-pointer uppercase tracking-wider text-sm"
        >
          {loading ? <span>Verifying ID...</span> : <span>Search Database</span>}
        </button>
      </form>

      {/* Quick Test Chips */}
      <div className="flex flex-wrap items-center gap-3 mb-8 text-xs text-fintech-secondary font-medium">
        <span className="font-bold uppercase tracking-wider">Try sample IDs:</span>
        <button type="button" onClick={() => setRegNo('INH000005678')} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-md text-fintech-text font-mono transition-colors">INH000005678 (Valid)</button>
        <button type="button" onClick={() => setRegNo('INA000001234')} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-md text-fintech-text font-mono transition-colors">INA000001234 (Valid)</button>
        <button type="button" onClick={() => setRegNo('INA000004321')} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-md text-fintech-text font-mono transition-colors">INA000004321 (Suspended)</button>
        <button type="button" onClick={() => setRegNo('FAKE99999')} className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-md text-fintech-text font-mono transition-colors">FAKE99999 (Invalid)</button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-fintech-red rounded-xl text-sm font-semibold flex items-center shadow-sm">
           <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Verification Card Result */}
      {result && (
        <div className={`p-8 rounded-xl border-2 ${result.is_valid ? 'bg-fintech-soft border-fintech-green/30' : 'bg-red-50 border-fintech-red/30'} transition-all`}>
          <div className="flex items-center justify-between border-b border-black/10 pb-6 mb-6">
            <div className="flex items-center space-x-4">
              <div className={`p-4 rounded-xl shadow-sm bg-white ${result.is_valid ? 'text-fintech-green' : 'text-fintech-red'}`}>
                {result.is_valid ? <ShieldCheck className="w-8 h-8" /> : <ShieldAlert className="w-8 h-8" />}
              </div>
              <div>
                <span className="font-mono text-xs font-bold text-fintech-secondary uppercase tracking-widest block mb-1">Entity Reg ID: {result.reg_no}</span>
                <h3 className="text-2xl font-extrabold text-fintech-text">{result.name || 'Unregistered Entity'}</h3>
              </div>
            </div>

            <span className={`text-xs font-black uppercase tracking-widest px-4 py-2 rounded-sm border-2 ${
              result.status === 'VALID' ? 'bg-white text-fintech-green border-fintech-green' : 'bg-white text-fintech-red border-fintech-red'
            }`}>
              STATUS: {result.status}
            </span>
          </div>

          <p className="text-base font-medium text-fintech-secondary mb-6 leading-relaxed bg-white/50 p-4 rounded-lg border border-black/5">{result.details}</p>

          {result.is_valid && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-sm bg-white p-6 rounded-xl border border-black/10 shadow-sm">
              <div>
                <span className="text-xs uppercase tracking-widest text-fintech-secondary block font-bold mb-1">Category</span>
                <span className="font-bold text-fintech-text">{result.category}</span>
              </div>
              <div>
                <span className="text-xs uppercase tracking-widest text-fintech-secondary block font-bold mb-1">Associated Company</span>
                <span className="font-bold text-fintech-text">{result.company}</span>
              </div>
              <div>
                <span className="text-xs uppercase tracking-widest text-fintech-secondary block font-bold mb-1">Registration Validity</span>
                <span className="font-bold text-fintech-text">{result.valid_till}</span>
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
}
