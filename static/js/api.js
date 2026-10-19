/* ============================================================================
   FinGuard Transport Layer — Central API Service Module
   ----------------------------------------------------------------------------
   Connects the frontend to the existing backend and preserves all API contracts:
     POST /api/jobs                    multipart `file`  -> {job_id, status}
     GET  /api/jobs/{job_id}                             -> {status, stage, result, error}
     GET  /api/jobs/{job_id}/complaint                   -> text/plain
     POST /api/scan/audio              multipart `file`  -> full result (synchronous)
     POST /api/scan/image              multipart `file`  -> full result (synchronous)
     POST /api/scan/text               json {text}       -> full result (synchronous)
     POST /api/scan/url                json {url}        -> full result (synchronous)
     POST /api/scan/apk                multipart `file`  -> full result (synchronous)
     GET  /api/registry/status                           -> {total_records, last_sync, ...}
     GET  /api/health                                    -> {status, version, service}
   ========================================================================= */

import { ext } from './dom.js';
import { planFor } from './stages.js';

/* ── Environment & API Base URL Configuration ────────────────────────────── */

/**
 * Resolves the backend API base URL:
 * 1. window.FINGUARD_API_BASE or window.__FINGUARD_API_BASE__
 * 2. <meta name="finguard-api-base" content="...">
 * 3. localStorage.getItem('finguard_api_base')
 * 4. In development: if loaded from localhost:3000 (standalone frontend runner),
 *    defaults to http://localhost:8000 (FastAPI backend server)
 * 5. In production / same-origin: defaults to "" (relative path)
 */
export function getApiBase() {
  if (typeof window === 'undefined') return '';
  if (window.FINGUARD_API_BASE) {
    return String(window.FINGUARD_API_BASE).replace(/\/+$/, '');
  }
  if (window.__FINGUARD_API_BASE__) {
    return String(window.__FINGUARD_API_BASE).replace(/\/+$/, '');
  }
  const meta = document.querySelector('meta[name="finguard-api-base"]');
  if (meta && meta.getAttribute('content')) {
    return meta.getAttribute('content').replace(/\/+$/, '');
  }
  try {
    const stored = localStorage.getItem('finguard_api_base');
    if (stored) return stored.replace(/\/+$/, '');
  } catch (_) {
    // Storage access might be restricted in some iframe contexts
  }
  // Standalone frontend runner convention (port 3000 -> backend on port 8000)
  if (window.location && window.location.hostname === 'localhost' && window.location.port === '3000') {
    return 'http://localhost:8000';
  }
  return '';
}

/** Formats an absolute or relative API URL using the configured base. */
export function apiUrl(path) {
  const base = getApiBase();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${cleanPath}` : cleanPath;
}

/* ── Limits & Validation Rules ───────────────────────────────────────────── */

export const LIMITS = {
  maxBytes: 100 * 1024 * 1024, // 100 MB max file size
  video: ['.mp4', '.avi', '.mov', '.mkv'],
  audio: ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac'],
  image: ['.jpg', '.jpeg', '.png', '.webp', '.bmp'],
  apk: ['.apk'],
  minTextChars: 5,
  minUrlChars: 3,
};

export class ServiceError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ServiceError';
    this.status = status;
    this.details = details;
  }
}

async function readError(response) {
  let detail = '';
  let parsed = null;
  try {
    parsed = await response.json();
    detail = typeof parsed?.detail === 'string'
      ? parsed.detail
      : (parsed?.error || JSON.stringify(parsed?.detail ?? parsed));
  } catch (_) {
    detail = await response.text().catch(() => '');
  }
  const fallbackMessage = response.status === 413
    ? 'The uploaded file exceeds the 100 MB size limit.'
    : response.status === 404
      ? 'The requested analysis or service endpoint was not found.'
      : response.status >= 500
        ? 'The analysis service encountered an internal error. Please try again.'
        : `Request failed with status code ${response.status}.`;
  return new ServiceError(detail || fallbackMessage, response.status, parsed);
}

async function asJson(response) {
  if (!response.ok) throw await readError(response);
  return response.json();
}

/* ── Core API Endpoints ──────────────────────────────────────────────────── */

export async function health(signal) {
  const res = await fetch(apiUrl('/api/health'), { cache: 'no-store', signal });
  return asJson(res);
}

export async function registryStatus(signal) {
  const res = await fetch(apiUrl('/api/registry/status'), { cache: 'no-store', signal });
  return asJson(res);
}

async function postMultipart(path, file, signal) {
  const form = new FormData();
  form.append('file', file, file.name);
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    body: form,
    signal,
  });
  return asJson(res);
}

export const createVideoJob = (file, signal) => postMultipart('/api/jobs', file, signal);
export const scanAudio      = (file, signal) => postMultipart('/api/scan/audio', file, signal);
export const scanImage      = (file, signal) => postMultipart('/api/scan/image', file, signal);
export const scanApk        = (file, signal) => postMultipart('/api/scan/apk', file, signal);

export async function scanText(text, signal) {
  const res = await fetch(apiUrl('/api/scan/text'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  });
  return asJson(res);
}

export async function scanUrl(url, signal) {
  const res = await fetch(apiUrl('/api/scan/url'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
    signal,
  });
  return asJson(res);
}

export async function getJob(jobId, signal) {
  const res = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(jobId)}`), {
    cache: 'no-store',
    signal,
  });
  return asJson(res);
}

export async function getJobComplaint(jobId, signal) {
  const res = await fetch(apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/complaint`), {
    cache: 'no-store',
    signal,
  });
  if (!res.ok) throw await readError(res);
  return res.text();
}

/** URL for direct browser download of a completed job's complaint draft. */
export const complaintUrl = (jobId) => apiUrl(`/api/jobs/${encodeURIComponent(jobId)}/complaint`);

/* ── Client-Side Input Validation ────────────────────────────────────────── */

export function validateFile(mode, file) {
  const allowed = LIMITS[mode];
  if (!allowed) return { ok: false, message: `Unsupported scan type: ${mode}.` };
  if (!file) return { ok: false, message: 'Please select a file to analyze.' };

  const fileExt = ext(file.name);
  if (!allowed.includes(fileExt)) {
    return {
      ok: false,
      message: `File format "${fileExt || 'unknown'}" is not supported for ${mode} scans. Accepted formats: ${allowed.join(', ')}.`,
    };
  }
  if (file.size > LIMITS.maxBytes) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return {
      ok: false,
      message: `The selected file is ${sizeMb} MB. Maximum upload limit is 100 MB.`,
    };
  }
  if (file.size === 0) {
    return { ok: false, message: 'The selected file is empty (0 bytes).' };
  }
  return { ok: true };
}

export function validateText(text) {
  const trimmed = (text || '').trim();
  if (trimmed.length < LIMITS.minTextChars) {
    return {
      ok: false,
      message: `Text must contain at least ${LIMITS.minTextChars} characters for meaningful analysis.`,
    };
  }
  return { ok: true };
}

export function validateUrl(url) {
  const trimmed = (url || '').trim();
  if (trimmed.length < LIMITS.minUrlChars) {
    return { ok: false, message: 'Please enter a valid website address or domain.' };
  }
  const hasDot = trimmed.includes('.');
  if (!hasDot) {
    return { ok: false, message: 'Please enter a complete domain or URL (e.g. https://example.com).' };
  }
  return { ok: true };
}

/* ── Analysis Orchestration & Job Polling ────────────────────────────────── */

/**
 * Initiates and tracks an analysis job across any supported modality.
 * Handles video via backend job polling, and synchronous endpoints with honest progress tracking.
 *
 * @param {'video'|'audio'|'image'|'text'|'url'|'apk'} mode
 * @param {File|string} payload
 * @param {object} handlers
 * @returns {{ cancel: () => void }}
 */
export function startRun(mode, payload, handlers) {
  const plan = planFor(mode);
  const controller = new AbortController();
  let stopped = false;
  let activePollTimeout = null;

  const emit = {
    job: (jobId) => handlers.onJob?.(jobId),
    stage: (index, state) => handlers.onStage?.(index, state),
    progress: (fraction) => handlers.onProgress?.(Math.max(0, Math.min(1, fraction))),
    status: (text) => handlers.onStatus?.(text),
  };

  const finish = (result) => {
    if (stopped) return;
    stopped = true;
    if (activePollTimeout) clearTimeout(activePollTimeout);
    handlers.onDone?.(result);
  };

  const fail = (error) => {
    if (stopped) return;
    stopped = true;
    if (activePollTimeout) clearTimeout(activePollTimeout);
    if (error?.name === 'AbortError') return;
    handlers.onError?.(error);
  };

  /* ── Video: Asynchronous Job Polling ───────────────────────────────────── */
  async function pollingSource() {
    let jobData;
    try {
      jobData = await createVideoJob(payload, controller.signal);
    } catch (err) {
      return fail(err);
    }

    const jobId = jobData.job_id;
    emit.job(jobId);
    let stageIndex = 0;
    emit.stage(0, 'active');
    emit.status(plan[0]?.status || 'Securing media and extracting frames...');

    let pollAttempts = 0;
    const maxPollAttempts = 360; // Up to ~6 minutes of polling
    let consecutiveDropCount = 0;

    const poll = async () => {
      if (stopped) return;
      pollAttempts += 1;

      if (pollAttempts > maxPollAttempts) {
        return fail(new ServiceError('The analysis exceeded the maximum allowed time. Please retry with a shorter clip.', 408));
      }

      let job;
      try {
        job = await getJob(jobId, controller.signal);
        consecutiveDropCount = 0;
      } catch (err) {
        if (err?.name === 'AbortError') return;
        if (err?.status === 404) return fail(err);
        consecutiveDropCount += 1;
        // Allow up to 3 momentary network hiccups before failing
        if (consecutiveDropCount >= 4) {
          return fail(new ServiceError('Network connection to the analysis service was interrupted.', 0));
        }
        activePollTimeout = setTimeout(poll, 2500);
        return;
      }

      // Sync stage progress with real backend stage state
      const reportedIndex = plan.findIndex((s) => s.key === job.stage);
      if (reportedIndex > stageIndex) {
        for (let i = stageIndex; i < reportedIndex; i += 1) emit.stage(i, 'done');
        stageIndex = reportedIndex;
        emit.stage(stageIndex, 'active');
        emit.status(plan[stageIndex]?.status || 'Processing...');
      }

      // Calculate honest fraction based on verified completed stages
      const baseProgress = stageIndex / Math.max(1, plan.length);
      emit.progress(baseProgress);

      if (job.status === 'completed' && job.result) {
        plan.forEach((_, i) => emit.stage(i, 'done'));
        emit.progress(1.0);
        return finish(job.result);
      }

      if (job.status === 'failed') {
        emit.stage(stageIndex, 'failed');
        const failureMessage = job.error || 'The analysis service could not process this video.';
        return fail(new ServiceError(failureMessage, 500));
      }

      activePollTimeout = setTimeout(poll, 1200);
    };

    activePollTimeout = setTimeout(poll, 800);
  }

  /* ── Synchronous Endpoints (Audio, Image, Text, URL, APK) ──────────────── */
  function synchronousSource(requestFn) {
    emit.stage(0, 'active');
    emit.status(plan[0]?.status || 'Executing forensic scan...');
    // Indeterminate progress representation for synchronous requests
    emit.progress(0.15);

    requestFn(controller.signal)
      .then((result) => {
        if (stopped) return;
        plan.forEach((_, i) => emit.stage(i, 'done'));
        emit.progress(1.0);
        finish(result);
      })
      .catch((err) => {
        fail(err);
      });
  }

  const runMap = {
    video: pollingSource,
    audio: () => synchronousSource((signal) => scanAudio(payload, signal)),
    image: () => synchronousSource((signal) => scanImage(payload, signal)),
    text:  () => synchronousSource((signal) => scanText(payload, signal)),
    url:   () => synchronousSource((signal) => scanUrl(payload, signal)),
    apk:   () => synchronousSource((signal) => scanApk(payload, signal)),
  };

  const execute = runMap[mode] || pollingSource;
  Promise.resolve().then(execute).catch(fail);

  return {
    cancel() {
      if (stopped) return;
      stopped = true;
      if (activePollTimeout) clearTimeout(activePollTimeout);
      controller.abort();
    },
  };
}
