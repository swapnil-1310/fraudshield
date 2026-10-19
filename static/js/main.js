/* ============================================================================
   FinGuard Main Application Controller
   ----------------------------------------------------------------------------
   Implements:
     - SPA Routing (/, /how-it-works, /features, /technology, /analyze, /analysis, /results)
     - Responsive Banking Navigation & Health Monitoring
     - Multi-Modal Form Handlers (Video, Audio, Image, Text, URL, APK)
     - 3D Security Shield Loading Scene & 18 Rotating Scam-Awareness Tips
     - Structured Result Presentation with Strict Modality Separation
   ========================================================================= */

import { $, $$, esc, fmtBytes, fmtClock, fmtScore, fmtStamp, reducedMotion } from './dom.js';
import { LIMITS, complaintUrl, health, startRun, validateFile, validateText, validateUrl } from './api.js';
import { planFor } from './stages.js';
import { toViewModel } from './model.js';

/* ── Application State ───────────────────────────────────────────────────── */

const state = {
  route: getInitialRoute(),
  mode: 'video',
  file: null,
  previewUrl: null,
  text: '',
  urlText: '',
  run: null,
  startedAt: null,
  jobId: null,
  viewModel: null,
  tipIndex: 0,
  tipTimer: null,
};

function getInitialRoute() {
  const path = window.location.pathname;
  const validRoutes = ['/', '/how-it-works', '/features', '/technology', '/analyze', '/analysis', '/results'];
  return validRoutes.includes(path) ? path : '/';
}

/* ── 18 Comprehensive Scam-Awareness Tips ────────────────────────────────── */

const SCAM_TIPS = [
  'Never share your OTP, even with someone claiming to be from your bank or regulatory authority.',
  'A promise of guaranteed high or fixed market returns is an immediate warning sign of investment fraud.',
  'Never transfer money to unlock a frozen investment withdrawal or pay an advance fee.',
  'Always check investment adviser claims through official SEBI sources at sebi.gov.in before investing.',
  'A familiar face or voice does not prove that a video or call is genuine. AI cloning is widely used by scammers.',
  'Never enter your UPI PIN to receive money. A PIN is required only when transferring funds out.',
  'Check website URLs carefully before entering financial details. Scammers create realistic lookalike domains.',
  'A genuine person can promote an unregistered scam, and AI-generated content can also be completely harmless.',
  'Legitimate investment advisers never ask for your Demat trading account password or authentication credentials.',
  'Be cautious of investment opportunities offered exclusively through private WhatsApp or Telegram groups.',
  'Government regulators and law enforcement agencies never demand instant funds transfers over the phone.',
  'High pressure to act immediately is one of the most common psychological tactics used in financial scams.',
  'Verify SEBI registration numbers on the official SEBI intermediary database before making commitments.',
  'Never install remote-access apps (such as AnyDesk or TeamViewer) at the request of an unknown caller.',
  'If an investment offer sounds too good to be true, pause and consult an independent registered professional.',
  'Deepfake audio can realistically mimic family members, corporate executives, or famous market commentators.',
  'Real stock exchanges and depositories never hold investor funds in personal savings accounts.',
  'Report financial cyber fraud immediately to the National Cyber Crime Portal at cybercrime.gov.in or helpline 1930.',
];

/* ── Routing & Navigation ────────────────────────────────────────────────── */

function showRoute(route) {
  state.route = route;
  if (window.location.pathname !== route) {
    history.pushState({}, '', route);
  }

  // View visibility
  $('#view-landing').hidden = route !== '/';
  $('#view-how').hidden = route !== '/how-it-works';
  $('#view-features').hidden = route !== '/features';
  $('#view-technology').hidden = route !== '/technology';
  $('#view-analyze').hidden = route !== '/analyze';
  $('#view-analysis').hidden = route !== '/analysis';
  $('#view-results').hidden = route !== '/results';

  // Highlight active nav links
  $$('.fg-nav__link').forEach((link) => {
    link.classList.toggle('fg-nav__link--active', link.dataset.route === route);
  });

  // Close mobile drawer
  $('#nav-header').removeAttribute('data-mobile-open');

  // Route-specific triggers
  if (route === '/analyze') {
    renderWorkspace();
  } else if (route === '/results' && state.viewModel) {
    renderReport(state.viewModel);
  }

  window.scrollTo({ top: 0, behavior: reducedMotion() ? 'auto' : 'smooth' });
}

function bindNavigation() {
  document.addEventListener('click', (e) => {
    const routeTarget = e.target.closest('[data-route]');
    if (routeTarget) {
      e.preventDefault();
      showRoute(routeTarget.dataset.route);
    }
  });

  window.addEventListener('popstate', () => {
    showRoute(getInitialRoute());
  });

  // Mobile menu toggle
  const toggleBtn = $('#nav-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const header = $('#nav-header');
      const isOpen = header.getAttribute('data-mobile-open') === 'true';
      if (isOpen) {
        header.removeAttribute('data-mobile-open');
      } else {
        header.setAttribute('data-mobile-open', 'true');
      }
    });
  }
}

/* ── Service Health Check ────────────────────────────────────────────────── */

function monitorHealth() {
  const healthPill = $('#health');
  const healthText = $('#health-text');

  health()
    .then((data) => {
      if (data && data.status === 'ok') {
        healthPill.dataset.state = 'online';
        healthText.textContent = 'System Online';
      } else {
        healthPill.dataset.state = 'online';
        healthText.textContent = 'Service Ready';
      }
    })
    .catch(() => {
      healthPill.dataset.state = 'offline';
      healthText.textContent = 'Service Offline';
    });
}

/* ── Analysis Workspace (Forms & Inputs) ─────────────────────────────────── */

function renderWorkspace() {
  const slot = $('#workspace-slot');
  const plan = planFor(state.mode);

  // Update sidebar stages list
  $('#sidebar-plan-title').textContent = `${state.mode.toUpperCase()} Inspection Plan`;
  $('#sidebar-stages-list').innerHTML = plan
    .map((stage, idx) => `
      <li class="fg-stages-list__item">
        <span class="fg-stages-list__idx">${String(idx + 1).padStart(2, '0')}</span>
        <div class="fg-stages-list__text">
          <b>${esc(stage.label)}</b>
          <span>${esc(stage.sub)}</span>
        </div>
      </li>
    `)
    .join('');

  // Update tab selection
  $$('.fg-tab').forEach((tab) => {
    tab.setAttribute('aria-selected', String(tab.dataset.mode === state.mode));
  });

  clearWorkspaceError();

  // Mode: Text
  if (state.mode === 'text') {
    slot.innerHTML = `
      <div class="fg-input-box">
        <label for="text-input" style="font-weight:600;font-size:0.875rem;display:block;margin-bottom:0.4rem;">
          Financial Message or Claim Text
        </label>
        <textarea class="fg-textarea" id="text-input" placeholder="Paste a financial message, social media tip, or claimed investment guarantee here...">${esc(state.text)}</textarea>
        <div class="fg-counter-row">
          <span>Minimum 5 characters for compliance analysis</span>
          <span id="text-counter">${state.text.length} characters</span>
        </div>
        <div style="margin-top:1.25rem;display:flex;justify-content:flex-end;">
          <button class="fg-btn" id="submit-text-btn" type="button">
            Analyze Text
          </button>
        </div>
      </div>
    `;

    const textarea = $('#text-input');
    textarea.addEventListener('input', () => {
      state.text = textarea.value;
      $('#text-counter').textContent = `${state.text.length} characters`;
    });

    $('#submit-text-btn').addEventListener('click', () => {
      const check = validateText(state.text);
      if (!check.ok) return showWorkspaceError(check.message);
      clearWorkspaceError();
      launchAnalysis();
    });
    return;
  }

  // Mode: URL
  if (state.mode === 'url') {
    slot.innerHTML = `
      <div class="fg-input-box">
        <label for="url-input" style="font-weight:600;font-size:0.875rem;display:block;margin-bottom:0.4rem;">
          Website Address or Domain
        </label>
        <input class="fg-input-url" id="url-input" type="url" placeholder="https://example-broker.com" value="${esc(state.urlText)}">
        <div class="fg-counter-row">
          <span>Checks against registered SEBI broker domains and known phishing signatures</span>
          <span id="url-counter">${state.urlText.length} characters</span>
        </div>
        <div style="margin-top:1.25rem;display:flex;justify-content:flex-end;">
          <button class="fg-btn" id="submit-url-btn" type="button">
            Audit URL
          </button>
        </div>
      </div>
    `;

    const urlInput = $('#url-input');
    urlInput.addEventListener('input', () => {
      state.urlText = urlInput.value;
      $('#url-counter').textContent = `${state.urlText.length} characters`;
    });

    $('#submit-url-btn').addEventListener('click', () => {
      const check = validateUrl(state.urlText);
      if (!check.ok) return showWorkspaceError(check.message);
      clearWorkspaceError();
      launchAnalysis();
    });
    return;
  }

  // Modes: Video, Audio, Image, APK
  if (state.file) {
    // Render selected file details
    slot.innerHTML = `
      <div class="fg-selected-file">
        <div class="fg-selected-file__meta">
          <div>
            <div class="fg-selected-file__label">Selected File</div>
            <div class="fg-selected-file__val" title="${esc(state.file.name)}">${esc(state.file.name)}</div>
          </div>
          <div>
            <div class="fg-selected-file__label">Content Type</div>
            <div class="fg-selected-file__val">${state.mode.toUpperCase()}</div>
          </div>
          <div>
            <div class="fg-selected-file__label">File Size</div>
            <div class="fg-selected-file__val">${fmtBytes(state.file.size)}</div>
          </div>
        </div>
        <div class="fg-selected-file__actions">
          <button class="fg-btn fg-btn--secondary" id="replace-file-btn" type="button">
            Replace File
          </button>
          <button class="fg-btn fg-btn--secondary" id="remove-file-btn" type="button">
            Remove
          </button>
          <button class="fg-btn" id="submit-file-btn" type="button">
            Analyze Now
          </button>
        </div>
      </div>
    `;

    $('#replace-file-btn').addEventListener('click', () => {
      state.file = null;
      renderWorkspace();
    });

    $('#remove-file-btn').addEventListener('click', () => {
      state.file = null;
      renderWorkspace();
    });

    $('#submit-file-btn').addEventListener('click', () => {
      launchAnalysis();
    });
    return;
  }

  // Render dropzone
  const allowed = (LIMITS[state.mode] || []).join(', ');
  const modeLabel = state.mode === 'apk' ? 'Android APK package' : `${state.mode} file`;

  slot.innerHTML = `
    <label class="fg-dropzone" id="file-dropzone" for="file-upload">
      <input class="fg-dropzone__input" id="file-upload" type="file" accept="${LIMITS[state.mode]?.join(',')}">
      <svg class="fg-dropzone__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      <div class="fg-dropzone__title">Select or drag a ${modeLabel}</div>
      <div class="fg-dropzone__desc">Click to browse your device or drag and drop your file here</div>
      <div class="fg-dropzone__formats">
        ${(LIMITS[state.mode] || []).map((ext) => `<span class="fg-dropzone__pill">${ext.toUpperCase().replace('.', '')}</span>`).join('')}
      </div>
      <div class="fg-dropzone__limit">Maximum allowed file size: 100 MB</div>
    </label>
  `;

  const fileInput = $('#file-upload');
  const dropzone = $('#file-dropzone');

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) {
      handleSelectedFile(fileInput.files[0]);
    }
  });

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.dataset.dragging = 'true';
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.dataset.dragging = 'false';
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });
}

function handleSelectedFile(file) {
  const check = validateFile(state.mode, file);
  if (!check.ok) {
    return showWorkspaceError(check.message);
  }
  clearWorkspaceError();

  if (state.previewUrl) {
    URL.revokeObjectURL(state.previewUrl);
  }

  state.file = file;
  if (file.type.startsWith('video/') || file.type.startsWith('audio/') || file.type.startsWith('image/')) {
    state.previewUrl = URL.createObjectURL(file);
  } else {
    state.previewUrl = null;
  }

  renderWorkspace();
}

function showWorkspaceError(msg) {
  const errBox = $('#workspace-error');
  errBox.hidden = false;
  errBox.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span>${esc(msg)}</span>
  `;
}

function clearWorkspaceError() {
  const errBox = $('#workspace-error');
  errBox.hidden = true;
  errBox.textContent = '';
}

/* ── Analysis Execution & Loading Orchestration ──────────────────────────── */

function launchAnalysis() {
  if (state.run) {
    state.run.cancel();
  }

  state.startedAt = new Date();
  state.jobId = null;
  state.viewModel = null;

  showRoute('/analysis');

  const payload = state.mode === 'text'
    ? state.text
    : state.mode === 'url'
      ? state.urlText
      : state.file;

  const displayName = state.mode === 'text'
    ? 'Pasted Financial Text'
    : state.mode === 'url'
      ? state.urlText
      : state.file ? state.file.name : 'Submitted Content';

  $('#loading-filename').textContent = displayName;

  // Set up loading screen state
  const isVideo = state.mode === 'video';
  const track = $('#loading-track');
  const bar = $('#loading-bar');
  const statusText = $('#loading-status-text');

  if (isVideo) {
    track.dataset.indeterminate = 'false';
    bar.style.width = '0%';
    statusText.textContent = 'Securing media and extracting frames...';
  } else {
    // Synchronous requests have indeterminate progress
    track.dataset.indeterminate = 'true';
    bar.style.width = '40%';
    statusText.textContent = 'Executing forensic analysis...';
  }

  startTipRotation();

  // Cancel button
  $('#cancel-analysis-btn').onclick = () => {
    if (state.run) state.run.cancel();
    stopTipRotation();
    showRoute('/analyze');
  };

  // Launch the analysis run via api.js
  state.run = startRun(state.mode, payload, {
    onJob: (jobId) => {
      state.jobId = jobId;
    },
    onProgress: (fraction) => {
      if (isVideo) {
        const pct = Math.round(fraction * 100);
        bar.style.width = `${pct}%`;
        track.setAttribute('aria-valuenow', String(pct));
      }
    },
    onStatus: (text) => {
      statusText.textContent = text;
    },
    onDone: (result) => {
      stopTipRotation();
      handleAnalysisSuccess(result);
    },
    onError: (err) => {
      stopTipRotation();
      handleAnalysisError(err);
    },
  });
}

function handleAnalysisSuccess(result) {
  try {
    state.viewModel = toViewModel(result, {
      mode: state.mode,
      filename: state.mode === 'text'
        ? 'Pasted Text'
        : state.mode === 'url'
          ? state.urlText
          : state.file ? state.file.name : 'Submitted Content',
      jobId: state.jobId,
      size: state.file ? state.file.size : null,
      startedAt: state.startedAt,
    });
    showRoute('/results');
  } catch (err) {
    console.error('Error assembling view model:', err);
    showRoute('/analyze');
    showWorkspaceError('An error occurred while formatting the analysis results.');
  }
}

function handleAnalysisError(err) {
  showRoute('/analyze');
  const msg = err?.message || 'The analysis service could not complete your request. Please try again.';
  showWorkspaceError(msg);
}

/* ── Scam Awareness Tips Rotation ────────────────────────────────────────── */

function startTipRotation() {
  state.tipIndex = 0;
  displayCurrentTip();

  clearInterval(state.tipTimer);
  state.tipTimer = setInterval(() => {
    state.tipIndex = (state.tipIndex + 1) % SCAM_TIPS.length;
    displayCurrentTip();
  }, 5000);

  // Manual prev/next navigation
  $('#tip-prev-btn').onclick = () => {
    state.tipIndex = (state.tipIndex - 1 + SCAM_TIPS.length) % SCAM_TIPS.length;
    displayCurrentTip();
  };

  $('#tip-next-btn').onclick = () => {
    state.tipIndex = (state.tipIndex + 1) % SCAM_TIPS.length;
    displayCurrentTip();
  };
}

function stopTipRotation() {
  if (state.tipTimer) {
    clearInterval(state.tipTimer);
    state.tipTimer = null;
  }
}

function displayCurrentTip() {
  const tipContent = $('#tip-content');
  const tipCounter = $('#tip-counter');
  if (tipContent && tipCounter) {
    tipContent.style.opacity = '0';
    setTimeout(() => {
      tipContent.textContent = SCAM_TIPS[state.tipIndex];
      tipCounter.textContent = `Tip ${state.tipIndex + 1} of ${SCAM_TIPS.length}`;
      tipContent.style.opacity = '1';
    }, 150);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   RESULTS & FORENSIC REPORT RENDERING
   ═══════════════════════════════════════════════════════════════════════ */

function renderReport(vm) {
  const container = $('#report-container');

  const peakScoreDisplay = vm.peakSignal !== null ? `${Math.round(vm.peakSignal * 100)}%` : '—';
  const downloadUrl = vm.jobId ? complaintUrl(vm.jobId) : null;

  container.innerHTML = `
    <!-- Overall Assessment Banner -->
    <section class="fg-verdict-banner" data-tier="${vm.tier.key}">
      <div class="fg-verdict-grid">
        <div>
          <span class="fg-verdict-badge ${vm.tier.badgeClass}">
            ${esc(vm.verdictLabel)}
          </span>
          <h2 class="fg-verdict-title">${esc(vm.verdictLabel)}</h2>
          <p class="fg-verdict-summary">${esc(vm.overallSummary)}</p>
          <div class="fg-verdict-meta">
            <span>Content: <b>${esc(vm.filename)}</b></span>
            <span>Analyzed: <b>${fmtStamp(vm.startedAt)}</b></span>
            <span>Inspection Mode: <b>${esc(vm.mode.toUpperCase())}</b></span>
            ${vm.jobId ? `<span>Reference ID: <b>${esc(vm.jobId.slice(0, 8))}</b></span>` : ''}
          </div>
        </div>

        <!-- Gauge Box -->
        <div class="fg-gauge-box">
          <div class="fg-gauge-score">${peakScoreDisplay}</div>
          <div class="fg-gauge-label">${esc(vm.peakSignalLabel)}</div>
        </div>
      </div>

      <div style="margin-top:1.25rem;display:flex;gap:0.75rem;flex-wrap:wrap;">
        <button class="fg-btn fg-btn--secondary" type="button" data-route="/analyze">
          Analyze Another File
        </button>
        ${downloadUrl ? `
          <a class="fg-btn" href="${downloadUrl}" download="SEBI_SCORES_Complaint_${esc(vm.jobId || 'draft')}.txt">
            Download Complaint Draft
          </a>
        ` : ''}
      </div>
    </section>

    <!-- Modality Scorecards Grid -->
    <div class="fg-section-header">
      <span class="fg-section-header__eyebrow">Modality Breakdown</span>
      <h3 class="fg-section-header__title" style="font-size:1.25rem;">Detector-Specific Findings</h3>
      <p class="fg-section-header__desc">Each detector operates independently. Scores are not combined or fabricated.</p>
    </div>

    <div class="fg-modalities-grid">
      <!-- 1. Video Authenticity -->
      <article class="fg-modality-card">
        <div class="fg-modality-card__head">
          <h4 class="fg-modality-card__title">Video Authenticity</h4>
          <span class="fg-modality-card__badge ${vm.videoModality.isFlagged ? 'fg-badge--high' : vm.videoModality.available ? 'fg-badge--safe' : 'fg-badge--idle'}">
            ${esc(vm.videoModality.scoreFormatted)}
          </span>
        </div>
        <div class="fg-modality-card__body">
          <div class="fg-modality-card__status">${esc(vm.videoModality.status)}</div>
          <div class="fg-modality-card__desc">${esc(vm.videoModality.summary)}</div>
          ${vm.videoModality.details.length ? `
            <div class="fg-modality-card__details">
              ${vm.videoModality.details.map(d => `
                <div class="fg-detail-row">
                  <span>${esc(d.label)}</span>
                  <span>${esc(d.value)}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </article>

      <!-- 2. Audio Check -->
      <article class="fg-modality-card">
        <div class="fg-modality-card__head">
          <h4 class="fg-modality-card__title">${esc(vm.audioModality.title || 'Audio Check')}</h4>
          <span class="fg-modality-card__badge ${vm.audioModality.badgeClass || (vm.audioModality.isFlagged ? 'fg-badge--high' : vm.audioModality.available ? 'fg-badge--safe' : 'fg-badge--idle')}">
            ${esc(vm.audioModality.scoreFormatted)}
          </span>
        </div>
        <div class="fg-modality-card__body">
          <div class="fg-modality-card__status">${esc(vm.audioModality.status)}</div>
          <div class="fg-modality-card__desc">${esc(vm.audioModality.summary)}</div>
          ${vm.audioModality.details.length ? `
            <div class="fg-modality-card__details">
              ${vm.audioModality.details.map(d => `
                <div class="fg-detail-row">
                  <span>${esc(d.label)}</span>
                  <span>${esc(d.value)}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </article>

      <!-- 3. Scam Check -->
      <article class="fg-modality-card">
        <div class="fg-modality-card__head">
          <h4 class="fg-modality-card__title">${esc(vm.scamModality.title || 'Scam Check')}</h4>
          <span class="fg-modality-card__badge ${vm.scamModality.badgeClass || (vm.scamModality.isFlagged ? 'fg-badge--high' : vm.scamModality.available ? 'fg-badge--safe' : 'fg-badge--idle')}">
            ${esc(vm.scamModality.scoreFormatted)}
          </span>
        </div>
        <div class="fg-modality-card__body">
          <div class="fg-modality-card__status">${esc(vm.scamModality.status)}</div>
          <div class="fg-modality-card__desc">${esc(vm.scamModality.summary)}</div>
          <div class="fg-modality-card__details">
            <div class="fg-detail-row">
              <span>${esc(vm.scamModality.quotedLabel || 'Quoted Violations')}</span>
              <span>${vm.scamModality.quotedCount}</span>
            </div>
            ${vm.scamModality.signals.filter(s => s.active).map(s => `
              <div class="fg-detail-row">
                <span>${esc(s.label)}</span>
                <span style="color:var(--status-risk-text);font-weight:600;">Flagged (${s.score}%)</span>
              </div>
            `).join('')}
          </div>
        </div>
      </article>

      <!-- 4. SEBI Registry Verification -->
      <article class="fg-modality-card">
        <div class="fg-modality-card__head">
          <h4 class="fg-modality-card__title">SEBI Registry Verification</h4>
          <span class="fg-modality-card__badge ${vm.registryModality.isFlagged ? 'fg-badge--high' : vm.registryModality.tier === 'low' ? 'fg-badge--safe' : 'fg-badge--idle'}">
            ${esc(vm.registryModality.badge)}
          </span>
        </div>
        <div class="fg-modality-card__body">
          <div class="fg-modality-card__status">${esc(vm.registryModality.label)}</div>
          <div class="fg-modality-card__desc">${esc(vm.registryModality.summary)}</div>
          <div class="fg-modality-card__details">
            ${vm.registryModality.claimedName ? `
              <div class="fg-detail-row">
                <span>Claimed Name</span>
                <span>${esc(vm.registryModality.claimedName)}</span>
              </div>
            ` : ''}
            ${vm.registryModality.claimedNumber ? `
              <div class="fg-detail-row">
                <span>Claimed Number</span>
                <span>${esc(vm.registryModality.claimedNumber)}</span>
              </div>
            ` : ''}
            ${vm.registryModality.matchedName ? `
              <div class="fg-detail-row">
                <span>Registered Entity</span>
                <span>${esc(vm.registryModality.matchedName)}</span>
              </div>
            ` : ''}
          </div>
        </div>
      </article>
    </div>

    <!-- Quoted Evidence Audit Trail Table -->
    <section class="fg-evidence-section">
      <h3 style="font-size:1.15rem;margin-bottom:0.75rem;">Verified Evidence & Findings</h3>
      ${vm.evidence.length ? `
        <div class="fg-table-wrap">
          <table class="fg-table">
            <thead>
              <tr>
                <th style="width:60px;">ID</th>
                <th style="width:180px;">Signal Category</th>
                <th style="width:140px;">Source Module</th>
                <th>Observed Evidence / Quoted Statement</th>
                <th style="width:100px;">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              ${vm.evidence.map(item => `
                <tr>
                  <td><b>${esc(item.id)}</b></td>
                  <td>${esc(item.kind)}</td>
                  <td><span class="fg-card__tag">${esc(item.source)}</span></td>
                  <td>
                    <div>${esc(item.body)}</div>
                    ${item.quote ? `<div class="fg-quote-text">"${esc(item.quote)}"</div>` : ''}
                  </td>
                  <td>${item.timestamp !== null ? fmtClock(item.timestamp) : '—'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      ` : `
        <p style="color:var(--text-secondary);font-size:0.875rem;margin-bottom:0;">
          No explicit evidence items or regulatory violations were flagged for this submission.
        </p>
      `}
    </section>

    <!-- Recommended Next Steps -->
    <section class="fg-next-steps">
      <h3 class="fg-next-steps__title">Recommended Next Steps</h3>
      <ul class="fg-steps-list">
        ${vm.nextSteps.map(step => `
          <li class="fg-step-item">
            <svg class="fg-step-item__icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <div>
              <div class="fg-step-item__title">${esc(step.title)}</div>
              <p class="fg-step-item__desc">${esc(step.body)}</p>
            </div>
          </li>
        `).join('')}
      </ul>
    </section>

    <!-- Pre-Filing SEBI SCORES Complaint Draft -->
    ${vm.scoresComplaint ? `
      <section class="fg-complaint-box">
        <div class="fg-complaint-box__header">
          <h3 style="font-size:1.15rem;margin:0;">SEBI SCORES Complaint Draft (Pre-Filing Preview)</h3>
          <button class="fg-btn fg-btn--secondary fg-btn--sm" id="copy-complaint-btn" type="button">
            Copy Draft Text
          </button>
        </div>
        <div class="fg-complaint-notice">
          <b>Notice:</b> This draft has been generated automatically from the forensic findings above. It is provided for consumer convenience to assist when filing a formal complaint on the official SEBI SCORES portal (<a href="https://scores.sebi.gov.in" target="_blank">scores.sebi.gov.in</a>). It is not an officially submitted legal complaint.
        </div>
        <pre class="fg-complaint-pre" id="complaint-pre">${esc(vm.scoresComplaint)}</pre>
      </section>
    ` : ''}

    <div style="text-align:center;margin-top:2rem;">
      <button class="fg-btn fg-btn--secondary" type="button" data-route="/analyze">
        Start a New Analysis
      </button>
    </div>
  `;

  // Attach copy button handler
  const copyBtn = $('#copy-complaint-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const text = vm.scoresComplaint || '';
      navigator.clipboard.writeText(text).then(() => {
        copyBtn.textContent = 'Copied to Clipboard!';
        setTimeout(() => {
          copyBtn.textContent = 'Copy Draft Text';
        }, 2000);
      });
    });
  }
}

/* ── Application Initialisation ──────────────────────────────────────────── */

function init() {
  bindNavigation();
  monitorHealth();
  setInterval(monitorHealth, 30000);

  // Mode tab switching in workspace
  $$('.fg-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      state.mode = tab.dataset.mode;
      state.file = null;
      state.text = '';
      state.urlText = '';
      renderWorkspace();
    });
  });

  // Show starting route
  showRoute(state.route);
}

// Boot on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}