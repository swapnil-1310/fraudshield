/* ============================================================================
   FinGuard Model Adapter — Raw Backend Payload -> View Model
   ----------------------------------------------------------------------------
   Strictly separates:
     1. Overall Assessment
     2. Video Authenticity (Visual deepfake forensics)
     3. Audio Authenticity (Voice deepfake & cloning forensics)
     4. Scam or Misleading Financial Content (SEBI regulatory & fraud intent)
     5. Registry Verification (SEBI official database checks)
     6. Network & App Security (URLs, APKs, domains)
     7. Quoted Evidence & Findings Audit Trail
     8. Actionable Recommended Next Steps

   Verdicts mapped to simple, transparent consumer labels:
     - No clear warning signs found.
     - Review recommended.
     - Possible scam detected.
     - Possible AI-generated or altered content.
     - Analysis incomplete.
   ========================================================================= */

import { fmtClock } from './dom.js';

/* ── Verdict & Risk Tier Mapping ─────────────────────────────────────────── */

export const TIERS = {
  critical: { key: 'critical', label: 'Critical Risk', rank: 4, badgeClass: 'fg-badge--crit' },
  high:     { key: 'high',     label: 'High Risk',     rank: 3, badgeClass: 'fg-badge--high' },
  moderate: { key: 'moderate', label: 'Review Recommended', rank: 2, badgeClass: 'fg-badge--warn' },
  low:      { key: 'low',      label: 'Low Risk',      rank: 1, badgeClass: 'fg-badge--safe' },
  unknown:  { key: 'unknown',  label: 'Inconclusive',  rank: 0, badgeClass: 'fg-badge--idle' },
};

/**
 * Maps the backend's calibrated verdict string to simple, transparent labels
 * as required by banking guidelines.
 */
export function mapVerdictLabel(rawVerdict, isDeepfake, isScam, degraded = false) {
  if (degraded) return 'Analysis incomplete';
  const v = String(rawVerdict || '').toLowerCase();

  if (v.includes('deepfake + scam') || (isDeepfake && isScam)) {
    return 'Possible scam and AI-generated content detected';
  }
  if (v.includes('deepfake') || isDeepfake) {
    return 'Possible AI-generated or altered content';
  }
  if (v.includes('scam') || v.includes('violation') || isScam) {
    return 'Possible scam detected';
  }
  if (v.includes('review') || v.includes('suspicious')) {
    return 'Review recommended';
  }
  if (v.includes('safe') || v.includes('clean')) {
    return 'No clear warning signs found';
  }
  return 'Review recommended';
}

export function tierFromVerdict(verdict, degraded = false) {
  if (degraded) return TIERS.unknown;
  const v = String(verdict || '').toLowerCase();
  if (v.startsWith('critical')) return TIERS.critical;
  if (v.startsWith('warning')) return TIERS.high;
  if (v.startsWith('suspicious')) return TIERS.moderate;
  if (v.startsWith('safe')) return TIERS.low;
  return TIERS.unknown;
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const arr = (v) => (Array.isArray(v) ? v.filter(Boolean) : []);

export const SIGNAL_LABELS = {
  explicit_returns:  'Guaranteed returns',
  implied_returns:   'Implied returns',
  urgency_scarcity:  'Urgency and artificial deadlines',
  social_proof:      'Fabricated social proof',
  paywall_push:      'Directing to private/paid channels',
  credential_misrep: 'Credential & license misrepresentation',
};

const CLAIM_GROUPS = [
  {
    field: 'specific_return_promises',
    kind: 'Guaranteed Return Claim',
    tier: 'high',
    why: 'Promising or guaranteeing specific stock market returns violates SEBI regulations. Legitimate advisers cannot guarantee market returns.',
  },
  {
    field: 'implied_returns',
    kind: 'Implied Return',
    tier: 'moderate',
    why: 'Heavily implying risk-free or outsized gains creates false expectations while evading explicit legal guarantees.',
  },
  {
    field: 'urgency_scarcity_language',
    kind: 'Urgency & Pressure Tactic',
    tier: 'moderate',
    why: 'Creating pressure to invest immediately or claim limited spots is intended to prevent the investor from verifying credentials.',
  },
  {
    field: 'social_proof_inflation',
    kind: 'Exaggerated Social Proof',
    tier: 'moderate',
    why: 'Unsubstantiated claims of thousands of satisfied VIP members are frequently fabricated in investment scams.',
  },
  {
    field: 'paywall_push',
    kind: 'Private Channel / Paywall Push',
    tier: 'moderate',
    why: 'Directing viewers to private WhatsApp or Telegram groups is the standard pathway used by unregistered operators.',
  },
  {
    field: 'credential_misrepresentation',
    kind: 'Credential Claim',
    tier: 'high',
    why: 'Claiming fictitious registration or misrepresenting qualifications attempts to borrow false authority.',
  },
];

const REGISTRY_READING = {
  'verified': {
    tier: 'low',
    badge: 'Verified Entity',
    label: 'SEBI Registered Adviser Confirmed',
    text: 'The claimed adviser name and registration number match an active record in the SEBI intermediary registry.',
  },
  'not claimed': {
    tier: 'unknown',
    badge: 'No Claim Made',
    label: 'No Registration Number Claimed',
    text: 'The content did not claim a specific SEBI registration number or entity identity.',
  },
  'not found': {
    tier: 'moderate',
    badge: 'Unregistered Claim',
    label: 'Registration Number Not Found in Registry',
    text: 'The claimed name or registration number was not found in the official SEBI registry snapshot. Unregistered advice warrants caution.',
  },
  'malformed number': {
    tier: 'high',
    badge: 'Invalid Format',
    label: 'Malformed Registration Number',
    text: 'The quoted registration number does not adhere to official SEBI registration numbering standards.',
  },
  'name-number mismatch': {
    tier: 'critical',
    badge: 'Impersonation Flag',
    label: 'Registration Number Belongs to Different Entity',
    text: 'The registration number quoted exists in the registry, but belongs to a completely different entity. This indicates deliberate impersonation.',
  },
};

/** Extracts quote timestamps from timeline segments. */
function buildQuoteClock(raw) {
  const index = new Map();
  for (const entry of arr(raw.timeline_track)) {
    if (entry.quote) index.set(String(entry.quote).trim().toLowerCase(), entry.start);
  }
  const segments = arr(raw.segments);
  return (quote) => {
    const key = String(quote || '').trim().toLowerCase();
    if (!key) return null;
    if (index.has(key)) return index.get(key);
    const hit = segments.find((s) => {
      const text = String(s.text || '').toLowerCase();
      return text.includes(key) || (key.length > 12 && key.includes(text) && text.length > 6);
    });
    return hit ? hit.start : null;
  };
}

/* ── Clean Up Internal Diagnostics for User-Facing Explanations ───────────── */

function cleanDiagnosticTags(text) {
  if (!text) return '';
  return String(text)
    .replace(/\[HEURISTIC FALLBACK:[^\]]*\]\s*/gi, '')
    .replace(/\[REVIEW REQUIRED\]\s*/gi, '')
    .trim();
}

/* ── Recommended Next Steps Generator ────────────────────────────────────── */

function generateNextSteps(isDeepfake, isScam, registryVerdict, hasThreats) {
  const steps = [];

  if (isScam || hasThreats) {
    steps.push({
      priority: 'high',
      title: 'Do not transfer funds or share financial credentials',
      body: 'Never send money, share your UPI PIN, or provide Demat account login details. Legitimate registered entities never demand immediate wire transfers into private accounts.',
    });
    steps.push({
      priority: 'high',
      title: 'Report suspicious operators to SEBI and Cyber Crime',
      body: 'You can report unregistered entities directly on the SEBI SCORES 2.0 portal (scores.sebi.gov.in) and report cyber fraud to the National Cyber Crime Reporting Portal (cybercrime.gov.in or helpline 1930).',
    });
  }

  if (isDeepfake) {
    steps.push({
      priority: 'high',
      title: 'Verify identity through independent secondary channels',
      body: 'The voice or face in this media shows indicators of AI generation or manipulation. Do not trust familiar faces or executive voices in investment solicitations without independent confirmation.',
    });
  }

  if (registryVerdict === 'name-number mismatch' || registryVerdict === 'not found') {
    steps.push({
      priority: 'moderate',
      title: 'Independently check the SEBI Intermediary Database',
      body: 'Always verify investment advisers directly on the official SEBI website (sebi.gov.in) under "Recognised Intermediaries" before engaging in any advisory relationship.',
    });
  }

  if (steps.length === 0) {
    steps.push({
      priority: 'low',
      title: 'Maintain standard financial vigilance',
      body: 'While no overt scam indicators or synthetic manipulation were identified, always conduct independent due diligence before making investment decisions.',
    });
  }

  return steps;
}

/* ── Main Adapter Function ───────────────────────────────────────────────── */

/**
 * Converts a raw backend API payload into a structured, reliable view model.
 *
 * @param {object} raw   The response payload from any scan endpoint or completed job
 * @param {object} meta  { mode, filename, jobId, size, startedAt }
 */
export function toViewModel(raw, meta = {}) {
  const sebi = raw.sebi_analysis || {};
  const registry = raw.registry_check || {};
  const impersonation = raw.impersonation_check || {};
  const degradedModules = arr(raw.degraded_modules);
  const isDegraded = degradedModules.length > 0 && Boolean(raw.fallback_used);

  const isDeepfake = Boolean(raw.is_deepfake);
  const isScam = Boolean(raw.is_scam);
  const rawVerdict = String(raw.verdict || 'Suspicious: Review Recommended');
  const verdictLabel = mapVerdictLabel(rawVerdict, isDeepfake, isScam, isDegraded);
  const tier = tierFromVerdict(rawVerdict, isDegraded);
  const clockFor = buildQuoteClock(raw);

  const visionScore = num(raw.vision_score);
  const audioScore = num(raw.audio_score);
  const scamScore = num(raw.composite_risk_score);
  const flaggedAudio = arr(raw.flagged_audio_segments);
  const audioSegments = arr(raw.all_audio_segments);

  /* Attribute peak signal specifically without merging */
  const signalInputs = [
    { key: 'visual', label: 'Visual detector score', value: visionScore },
    { key: 'voice',  label: 'AI Voice Score',        value: audioScore },
    { key: 'scam',   label: 'Financial risk score',  value: scamScore },
  ].filter((s) => s.value !== null && Number.isFinite(s.value));

  const leadingSignal = signalInputs.length
    ? signalInputs.reduce((max, cur) => cur.value > max.value ? cur : max)
    : null;
  const peakSignal = leadingSignal ? leadingSignal.value : null;
  const peakSignalLabel = leadingSignal ? leadingSignal.label : 'Score';

  /* ── 1. Video Authenticity (Visual Forensics) ─────────────────────────── */
  let videoModality = null;
  if (visionScore === null) {
    videoModality = {
      available: false,
      title: 'Video Authenticity',
      status: 'Not examined',
      score: null,
      scoreFormatted: 'N/A',
      summary: 'This scan did not contain video frames, so visual forensic analysis was not performed.',
      isFlagged: false,
      heatmap: null,
      details: [],
    };
  } else {
    const isVisionFlagged = visionScore >= 0.50;
    videoModality = {
      available: true,
      title: 'Video Authenticity',
      status: isVisionFlagged ? 'Visual manipulation indicated' : 'No visual manipulation detected',
      score: visionScore,
      scoreFormatted: `${(visionScore * 100).toFixed(1)}%`,
      summary: isVisionFlagged
        ? 'Facial regions scored above the manipulation threshold. Spatial and frequency residuals indicate potential deepfake alterations.'
        : 'Sampled face frames scored below the visual manipulation threshold.',
      isFlagged: isVisionFlagged,
      heatmap: raw.heatmap_base64 || null,
      details: [
        { label: 'Visual Detector Score', value: `${(visionScore * 100).toFixed(1)}%` },
        { label: 'Evaluation Threshold', value: '50.0%' },
        { label: 'Temporal Variance', value: num(raw.vision_temporal_variance) !== null ? raw.vision_temporal_variance.toFixed(4) : 'N/A' },
      ],
    };
  }

  /* ── 2. Audio Check ─────────────────────────────────────────────────────── */
  let audioModality = null;
  if (audioScore === null) {
    audioModality = {
      available: false,
      title: 'Audio Check',
      status: 'Not examined',
      score: null,
      scoreFormatted: 'N/A',
      summary: 'No audio was found in this file.',
      isFlagged: false,
      flaggedCount: 0,
      totalWindows: 0,
      details: [],
    };
  } else {
    const isSynthetic = (raw.is_deepfake !== undefined && raw.is_deepfake !== null)
      ? raw.is_deepfake
      : (audioScore >= 0.50);
    const isAudioDegraded = degradedModules.includes('stage3_audio');
    const totalParts = audioSegments.length || 1;
    const flaggedParts = flaggedAudio.length;

    // Plain, everyday English status:
    // - "AI Voice Detected": classified as synthetic (score >= 0.50)
    // - "Could Not Confirm Voice Type": inconclusive / degraded
    // - "Human Voice Detected": classified as genuine
    let audioStatus = 'Human Voice Detected';
    let audioBadgeClass = 'fg-badge--safe';

    if (isSynthetic) {
      audioStatus = 'AI Voice Detected';
      audioBadgeClass = 'fg-badge--high';
    } else if (isAudioDegraded) {
      audioStatus = 'Could Not Confirm Voice Type';
      audioBadgeClass = 'fg-badge--warn';
    }

    let audioSummary = `All ${totalParts} evaluated audio parts show natural human voice patterns.`;
    if (audioStatus === 'AI Voice Detected') {
      audioSummary = `${flaggedParts} of ${totalParts} audio parts showed AI-generated voice characteristics (AI Voice Score: ${(audioScore * 100).toFixed(1)}%).`;
    } else if (audioStatus === 'Could Not Confirm Voice Type') {
      audioSummary = `Audio evaluation was inconclusive or operated in degraded mode. Voice type could not be confirmed with certainty.`;
    } else if (flaggedParts > 0) {
      audioSummary = `${totalParts - flaggedParts} of ${totalParts} audio parts confirmed natural human voice patterns (AI Voice Score: ${(audioScore * 100).toFixed(1)}%).`;
    }

    audioModality = {
      available: true,
      title: 'Audio Check',
      status: audioStatus,
      score: audioScore,
      scoreFormatted: `${(audioScore * 100).toFixed(1)}%`,
      summary: audioSummary,
      isFlagged: isAudioFlagged,
      badgeClass: audioBadgeClass,
      flaggedCount: flaggedParts,
      totalWindows: totalParts,
      impersonationTarget: impersonation.target || null,
      details: [
        { label: 'AI Voice Score', value: `${(audioScore * 100).toFixed(1)}%` },
        { label: 'Evaluation Threshold', value: '50.0%' },
        { label: 'Flagged Audio Parts', value: `${flaggedParts} of ${totalParts}` },
        ...(impersonation.target ? [{ label: 'Impersonation Target', value: impersonation.target }] : []),
      ],
    };
  }

  /* ── 3. Scam Check ──────────────────────────────────────────────────────── */
  const signalScores = sebi.signal_scores && typeof sebi.signal_scores === 'object' ? sebi.signal_scores : {};
  const totalQuotedClaims = CLAIM_GROUPS.reduce((n, g) => n + arr(sebi[g.field]).length, 0);

  const contentIntent = String(sebi.content_intent || raw.content_intent || '').toLowerCase();
  const analysisStatus = String(sebi.analysis_status || raw.analysis_status || '').toLowerCase();
  const speakerStance = String(sebi.speaker_stance || raw.speaker_stance || '').toLowerCase();
  const awarenessDetected = Boolean(sebi.awareness_context_detected || raw.awareness_context_detected);
  const isScamLikely = Boolean(sebi.is_scam_likely ?? raw.is_scam_likely ?? isScam);

  const isAwareness = (
    contentIntent === 'awareness_warning' ||
    (awarenessDetected && !isScamLikely) ||
    (speakerStance === 'warning' && !isScamLikely)
  );

  const isAmbiguous = !isScam && !isAwareness && (
    contentIntent === 'ambiguous' ||
    analysisStatus === 'conflict_review' ||
    speakerStance === 'ambiguous'
  );

  let scamStatus = 'No Scam Patterns Detected';
  let scamSummary = 'No fraudulent promises, pressure tactics, or scam patterns were identified in the spoken content.';
  let quotedLabel = 'Quoted Statements';

  if (isScam && !isAwareness) {
    scamStatus = 'Scam Warning';
    scamSummary = 'Speech or textual content contains high-risk promises, pressure tactics, or unauthorized investment advice.';
    quotedLabel = 'Quoted Violations';
  } else if (isAwareness) {
    scamStatus = 'Awareness / Educational Content';
    scamSummary = 'The speaker is warning listeners against financial scams, cautioning against fraud, or providing investor education.';
    quotedLabel = 'Quoted / Discussed Examples';
  } else if (isAmbiguous || isDegraded) {
    scamStatus = 'Needs Review';
    scamSummary = 'The content contains mixed, unverified, or unclear financial statements that require human review.';
    quotedLabel = 'Extracted Claims for Review';
  }

  const scamModality = {
    available: scamScore !== null,
    title: 'Scam Check',
    status: scamStatus,
    score: scamScore,
    scoreFormatted: scamScore !== null ? `${(scamScore * 100).toFixed(0)}%` : 'N/A',
    summary: scamSummary,
    isFlagged: isScam && !isAwareness,
    isReview: isAmbiguous || (isDegraded && !isScam && !isAwareness),
    isAwareness: isAwareness,
    badgeClass: (isScam && !isAwareness)
      ? 'fg-badge--high'
      : (isAmbiguous || (isDegraded && !isAwareness))
        ? 'fg-badge--warn'
        : (isAwareness || scamScore !== null)
          ? 'fg-badge--safe'
          : 'fg-badge--idle',
    quotedLabel,
    quotedCount: totalQuotedClaims,
    injectionDetected: Boolean(sebi.prompt_injection_detected),
    signals: Object.entries(SIGNAL_LABELS).map(([key, label]) => ({
      key,
      label,
      score: signalScores[key] !== undefined ? Math.round((signalScores[key] || 0) * 100) : 0,
      active: (signalScores[key] || 0) >= 0.35,
    })),
    segmentsAnalysis: arr(sebi.segments_analysis || raw.segments_analysis),
  };

  /* ── 4. SEBI Registry Verification ────────────────────────────────────── */
  const registryVerdict = String(registry.verdict || 'not claimed');
  const registryInfo = REGISTRY_READING[registryVerdict] || {
    tier: 'unknown',
    badge: registryVerdict,
    label: registryVerdict,
    text: 'The registry verification returned an unrecognised state.',
  };
  const matchedEntity = registry.matched_entity || null;
  const registryModality = {
    available: true,
    title: 'SEBI Registry Verification',
    verdict: registryVerdict,
    badge: registryInfo.badge,
    label: registryInfo.label,
    summary: registryInfo.text,
    tier: registryInfo.tier,
    isFlagged: registryInfo.tier === 'high' || registryInfo.tier === 'critical',
    claimedName: sebi.claimed_advisor_name || null,
    claimedNumber: sebi.claimed_registration_number || null,
    matchedName: matchedEntity?.name || null,
    matchedNumber: matchedEntity?.registration_number || null,
    matchedCategory: matchedEntity?.category || matchedEntity?.type || null,
  };

  /* ── 5. Network & App Security (URLs, Domains, APKs) ──────────────────── */
  const domScan = raw.domain_scan || {};
  const apkScan = raw.apk_analysis || raw.apk_result || {};
  const urlScan = raw.url_result || {};
  const hasNetworkThreats = Boolean(
    domScan.is_phishing ||
    urlScan.is_phishing ||
    apkScan.is_suspicious ||
    apkScan.suspicious
  );

  const networkModality = {
    available: Boolean(raw.domain_scan || raw.apk_analysis || raw.apk_result || raw.url_result),
    title: 'Network & Application Security',
    hasThreats: hasNetworkThreats,
    phishingDomain: domScan.domain || urlScan.domain || null,
    phishingReason: domScan.reason || urlScan.reason || null,
    targetBrand: domScan.closest_match || urlScan.closest_match || null,
    apkPackage: apkScan.package_name || null,
    dangerousPermissions: arr(apkScan.dangerous_permissions),
  };

  /* ── 6. Evidence Items Audit Trail ────────────────────────────────────── */
  const evidence = [];
  let seq = 0;
  const pushEvidence = (item) => {
    seq += 1;
    evidence.push({ id: `E${String(seq).padStart(2, '0')}`, ...item });
  };

  // Quoted claims from transcript / OCR
  for (const group of CLAIM_GROUPS) {
    for (const quote of arr(sebi[group.field])) {
      pushEvidence({
        kind: isAmbiguous ? `${group.kind} (Under Review)` : group.kind,
        tier: isAmbiguous ? 'moderate' : group.tier,
        source: 'Transcript / OCR Analysis',
        title: isAmbiguous ? `${group.kind} (Review Required)` : `${group.kind} detected`,
        body: isAmbiguous
          ? `Extracted claim under compliance review: ${group.why}`
          : group.why,
        quote: String(quote),
        timestamp: clockFor(quote),
      });
    }
  }

  // Audio segments flagged
  for (const seg of flaggedAudio) {
    pushEvidence({
      kind: 'AI Voice Segment',
      tier: (seg.score ?? 0) >= 0.75 ? 'high' : 'moderate',
      source: 'Audio Check',
      title: `Audio part scored ${Math.round((seg.score ?? 0) * 100)}% AI-generated`,
      body: 'This audio segment showed characteristics of AI-generated speech.',
      quote: null,
      timestamp: num(seg.start),
    });
  }

  // Visual frame manipulation
  if (visionScore !== null && visionScore >= 0.50) {
    pushEvidence({
      kind: 'Visual Forensic Anomaly',
      tier: visionScore >= 0.75 ? 'critical' : 'high',
      source: 'Face Manipulation Detector',
      title: `Face regions scored ${(visionScore * 100).toFixed(1)}% manipulation`,
      body: 'Spatial and noise residuals on detected facial regions exceeded the deepfake detection threshold.',
      quote: null,
      timestamp: null,
    });
  }

  // Registry issues
  if (registryInfo.tier === 'high' || registryInfo.tier === 'critical') {
    pushEvidence({
      kind: 'Registry Discrepancy',
      tier: registryInfo.tier,
      source: 'SEBI Registry Verification',
      title: registryInfo.label,
      body: registryInfo.text,
      quote: null,
      timestamp: null,
    });
  }

  // Network / Domain / APK threats
  if (domScan.is_phishing || urlScan.is_phishing) {
    pushEvidence({
      kind: 'Phishing Threat',
      tier: 'critical',
      source: 'Domain Forensics',
      title: `Suspicious domain: ${domScan.domain || urlScan.domain}`,
      body: domScan.reason || urlScan.reason || 'Domain impersonates a registered stockbroker platform.',
      quote: null,
      timestamp: null,
    });
  }

  if (apkScan.suspicious || apkScan.is_suspicious) {
    pushEvidence({
      kind: 'Rogue APK Threat',
      tier: 'critical',
      source: 'APK Forensics',
      title: `Suspicious application: ${apkScan.package_name || 'Rogue APK'}`,
      body: apkScan.reason || 'Application requests dangerous permissions without official broker certification.',
      quote: null,
      timestamp: null,
    });
  }

  /* ── 7. Overall Summary Construction ──────────────────────────────────── */
  let overallSummary = cleanDiagnosticTags(raw.overall_summary);
  if (!overallSummary) {
    const cleanedReasoning = cleanDiagnosticTags(sebi.reasoning);
    if (isDeepfake && isScam) {
      overallSummary = `High risk: Synthetic media detected alongside deceptive financial solicitations. ${cleanedReasoning}`;
    } else if (isDeepfake) {
      overallSummary = `Synthetic media detected by forensic detectors (${peakSignalLabel}: ${(peakSignal * 100).toFixed(0)}%). Spoken content contained no fraudulent claims: ${cleanedReasoning || 'General commentary with no high-risk SEBI violations flagged.'}`;
    } else if (isScam) {
      overallSummary = `Financial scam / SEBI regulatory violation flagged. Media showed no synthetic manipulation. ${cleanedReasoning}`;
    } else if (tier.key === 'moderate') {
      overallSummary = `Review recommended: The content or adviser credentials require independent verification. ${cleanedReasoning}`;
    } else {
      overallSummary = cleanedReasoning || 'No clear warning signs or synthetic manipulation were identified across the examined content.';
    }
  }

  /* ── 8. Next Steps ─────────────────────────────────────────────────────── */
  const nextSteps = generateNextSteps(isDeepfake, isScam, registryVerdict, hasNetworkThreats);

  /* ── 9. Interactive Transcript ─────────────────────────────────────────── */
  const transcriptSegments = arr(raw.segments).map((s) => ({
    start: num(s.start) ?? 0,
    end: num(s.end) ?? 0,
    text: String(s.text || ''),
  }));

  return {
    mode: meta.mode || raw.scan_type || 'video',
    jobId: meta.jobId || null,
    filename: meta.filename || (meta.mode === 'text' ? 'Pasted Text' : 'Submitted Content'),
    startedAt: meta.startedAt || new Date(),

    rawVerdict,
    verdictLabel,
    tier,
    isDegraded,
    degradedModules,

    peakSignal,
    peakSignalLabel,
    overallSummary,

    isDeepfake,
    isScam,

    // Distinct modalities
    videoModality,
    audioModality,
    scamModality,
    registryModality,
    networkModality,

    // Findings & Actions
    evidence,
    nextSteps,

    // Media & Transcripts
    transcript: transcriptSegments,
    transcriptText: String(raw.transcript || ''),
    segmentsAnalysis: arr(sebi.segments_analysis || raw.segments_analysis),
    scoresComplaint: raw.scores_complaint || null,

    raw,
  };
}

export const adaptJobResult = toViewModel;
