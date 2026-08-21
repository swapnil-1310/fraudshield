import React, { useState } from 'react';
import { Upload, Video, FileText, Loader2, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';

export default function MediaUploadModal({ onScanComplete }) {
  const [activeMode, setActiveMode] = useState('video'); // 'video' | 'text'
  const [selectedFile, setSelectedFile] = useState(null);
  const [textTip, setTextTip] = useState('');
  const [advisorRegNo, setAdvisorRegNo] = useState('');
  const [loading, setLoading] = useState(false);
  const [progressStep, setProgressStep] = useState('');
  const [error, setError] = useState('');

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (activeMode === 'video') {
        if (!selectedFile) {
          setError('Please select a video file (.mp4, .mov, .webm)');
          setLoading(false);
          return;
        }

        setProgressStep('Step 1/4: Sampling visual frames & running ViT Deepfake model...');
        
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('advisor_reg_no', advisorRegNo);

        setTimeout(() => setProgressStep('Step 2/4: Extracting audio track from video...'), 1500);
        setTimeout(() => setProgressStep('Step 3/4: Transcribing speech to text transcript...'), 3000);
        setTimeout(() => setProgressStep('Step 4/4: Evaluating spoken claims against SEBI guidelines...'), 4500);

        const res = await fetch('http://127.0.0.1:8000/api/scan-video', {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) throw new Error('Video scan failed. Please check server connection.');
        const data = await res.json();
        onScanComplete(data);

      } else {
        if (!textTip.trim()) {
          setError('Please enter investment tip text or social media post content');
          setLoading(false);
          return;
        }

        setProgressStep('Evaluating text against SEBI Prohibition of Fraudulent Practices...');

        const res = await fetch('http://127.0.0.1:8000/api/scan-text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: textTip, advisor_reg_no: advisorRegNo }),
        });

        if (!res.ok) throw new Error('Text analysis failed.');
        const data = await res.json();
        onScanComplete(data);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Error processing media scan');
    } finally {
      setLoading(false);
      setProgressStep('');
    }
  };

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 shadow-2xl my-6">
      
      {/* Mode Switcher */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Investigator Media Scanner</h2>
          <p className="text-xs text-slate-400 mt-1 font-medium">
            Scan video media or text tips for AI deepfake manipulation and SEBI compliance violations
          </p>
        </div>

        <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-xl border border-slate-800">
          <button
            type="button"
            onClick={() => setActiveMode('video')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === 'video' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Video className="w-4 h-4" />
            <span>Video & Audio Scan</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveMode('text')}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === 'text' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Text Tip Analysis</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        
        {/* Video Mode Dropzone */}
        {activeMode === 'video' ? (
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Select Investor Video File
            </label>
            <div className="relative border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-2xl p-8 text-center bg-slate-900/50 transition-all cursor-pointer group">
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex flex-col items-center">
                <div className="p-4 rounded-full bg-blue-500/10 text-blue-400 group-hover:scale-110 transition-transform">
                  <Upload className="w-8 h-8" />
                </div>
                <p className="mt-3 text-sm font-semibold text-white">
                  {selectedFile ? selectedFile.name : 'Click to select or drag video file here'}
                </p>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  Supports MP4, MOV, WEBM (Extracts visual deepfake frames + audio speech)
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Investment Advice / Tip Content
            </label>
            <textarea
              rows={4}
              value={textTip}
              onChange={(e) => setTextTip(e.target.value)}
              placeholder="Paste social media post, WhatsApp forward, or stock tip message here... (e.g. 'BUY $AAPL NOW! Guaranteed 100% returns in 7 days! Join VIP Telegram!')"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3.5 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors font-mono"
            />
          </div>
        )}

        {/* Optional SEBI Advisor Registration Number */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
            Claimed SEBI Registration Number (Optional)
          </label>
          <input
            type="text"
            value={advisorRegNo}
            onChange={(e) => setAdvisorRegNo(e.target.value)}
            placeholder="e.g. INH000005678 or INA000001234"
            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 font-mono"
          />
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-3 rounded-xl text-xs font-semibold flex items-center">
            <AlertTriangle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Progress Step */}
        {loading && (
          <div className="bg-blue-500/10 border border-blue-500/30 text-blue-400 p-3.5 rounded-xl text-xs font-semibold flex items-center space-x-3 animate-pulse">
            <Loader2 className="w-5 h-5 animate-spin flex-shrink-0 text-blue-400" />
            <span>{progressStep}</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-500 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-blue-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50 cursor-pointer"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Analyzing Media & SEBI Rules...</span>
            </>
          ) : (
            <>
              <span>Run Dual Visual & Audio SEBI Analysis</span>
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>

      </form>

    </div>
  );
}
