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
        
        // Add local video URL for real-time playback
        data.videoUrl = URL.createObjectURL(selectedFile);
        
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
    <div className="fintech-card p-8">
      
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-fintech-text tracking-tight uppercase">Dual Scanner</h2>
        <p className="text-sm text-fintech-secondary font-medium mt-1">
          Analyze suspicious financial content across visual, audio and text signals.
        </p>
      </div>

      {/* Mode Switcher */}
      <div className="flex space-x-4 mb-8">
        <button
          type="button"
          onClick={() => setActiveMode('video')}
          className={`flex-1 py-3 px-4 rounded-xl text-sm font-semibold border-2 transition-all ${
            activeMode === 'video'
              ? 'border-fintech-green bg-fintech-soft text-fintech-green'
              : 'border-fintech-border bg-white text-fintech-secondary hover:border-fintech-green/30 hover:text-fintech-text'
          }`}
        >
          <div className="flex items-center justify-center space-x-2">
            <Video className="w-5 h-5" />
            <span>VIDEO & AUDIO</span>
          </div>
          {activeMode === 'video' && <div className="mt-2 w-8 h-1 bg-fintech-green rounded-full mx-auto" />}
        </button>
        <button
          type="button"
          onClick={() => setActiveMode('text')}
          className={`flex-1 py-3 px-4 rounded-xl text-sm font-semibold border-2 transition-all ${
            activeMode === 'text'
              ? 'border-fintech-green bg-fintech-soft text-fintech-green'
              : 'border-fintech-border bg-white text-fintech-secondary hover:border-fintech-green/30 hover:text-fintech-text'
          }`}
        >
          <div className="flex items-center justify-center space-x-2">
            <FileText className="w-5 h-5" />
            <span>TEXT TIP</span>
          </div>
          {activeMode === 'text' && <div className="mt-2 w-8 h-1 bg-fintech-green rounded-full mx-auto" />}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        
        {/* Video Mode Dropzone */}
        {activeMode === 'video' ? (
          <div>
            <div className="relative border-2 border-dashed border-fintech-green/30 hover:border-fintech-green hover:bg-fintech-verysoft rounded-2xl p-10 text-center bg-white transition-all cursor-pointer group shadow-sm">
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <div className="flex flex-col items-center">
                <div className="p-4 rounded-full bg-fintech-soft text-fintech-green group-hover:-translate-y-1 transition-transform">
                  <Upload className="w-8 h-8" />
                </div>
                {selectedFile ? (
                  <div className="mt-4">
                    <p className="text-base font-bold text-fintech-text uppercase">{selectedFile.name}</p>
                    <p className="text-sm font-mono text-fintech-action mt-1">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB • READY FOR ANALYSIS</p>
                  </div>
                ) : (
                  <div className="mt-4">
                    <p className="text-base font-bold text-fintech-secondary uppercase tracking-widest">DROP VIDEO EVIDENCE</p>
                    <p className="text-sm font-medium text-fintech-secondary/70 mt-1">MP4 · MOV · WEBM</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div>
            <textarea
              rows={5}
              value={textTip}
              onChange={(e) => setTextTip(e.target.value)}
              placeholder="Paste a suspicious WhatsApp message, Telegram post, social media claim, or investment solicitation..."
              className="w-full bg-white border border-fintech-border rounded-xl p-4 text-base text-fintech-text focus:outline-none focus:border-fintech-green focus:ring-1 focus:ring-fintech-green shadow-sm transition-all"
            />
          </div>
        )}

        {/* Optional SEBI Advisor Registration Number */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-fintech-secondary mb-2">
            Claimed SEBI Registration Number <span className="text-fintech-secondary/60 lowercase">(Optional)</span>
          </label>
          <input
            type="text"
            value={advisorRegNo}
            onChange={(e) => setAdvisorRegNo(e.target.value)}
            placeholder="INA... / INH..."
            className="w-full bg-fintech-verysoft border border-fintech-border rounded-xl px-4 py-3 text-sm text-fintech-text focus:outline-none focus:border-fintech-green font-mono uppercase shadow-inner"
          />
          <p className="text-xs text-fintech-secondary mt-2">Used to cross-check the claimed regulatory identity.</p>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-fintech-red p-4 rounded-xl text-sm font-medium flex items-center shadow-sm">
            <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Intelligent Analysis Sequence */}
        {loading && (
          <div className="bg-white border border-fintech-border p-5 rounded-xl shadow-sm">
            <div className="flex items-center space-x-3 mb-2">
              <Loader2 className="w-5 h-5 animate-spin text-fintech-action" />
              <span className="font-bold text-fintech-text uppercase tracking-wider text-sm">Forensic Analysis</span>
            </div>
            <p className="text-sm font-mono text-fintech-action ml-8">{progressStep}</p>
            <div className="mt-3 w-full h-1 bg-fintech-soft rounded-full overflow-hidden">
               <div className="h-full bg-fintech-action w-1/2 animate-pulse rounded-full"></div>
            </div>
          </div>
        )}

        {/* Submit Button */}
        {!loading && (
          <button
            type="submit"
            className="w-full py-4 bg-fintech-action hover:bg-fintech-dark text-white font-bold rounded-xl shadow-[0_4px_14px_0_rgba(22,160,93,0.39)] hover:shadow-[0_6px_20px_rgba(22,160,93,0.23)] hover:-translate-y-0.5 flex items-center justify-center space-x-2 transition-all"
          >
            <span className="text-base tracking-wide">Run Forensic Analysis</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        )}

      </form>

    </div>
  );
}
