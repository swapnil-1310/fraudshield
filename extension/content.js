// FraudShield SEBI - WhatsApp/Telegram Live Shield

const scannedNodes = new WeakSet();

function injectBadge(element, verdictData) {
  // Prevent duplicate injections
  if (element.hasAttribute("data-fraudshield-scanned")) return;
  element.setAttribute("data-fraudshield-scanned", "true");

  if (!verdictData.is_sebi_violation) return; // Only inject if it's a violation

  const badge = document.createElement("div");
  badge.className = "fraudshield-sebi-badge";
  badge.innerHTML = `
    <div class="fs-header">
      <span class="fs-icon">🚨</span>
      <span class="fs-title">SEBI RISK: ${Math.round(verdictData.sebi_risk_score * 100)}%</span>
    </div>
    <div class="fs-reason">${verdictData.sebi_summary}</div>
  `;

  // Append badge right after the text node or inside the message bubble
  element.parentElement.appendChild(badge);
  
  // Highlight the message itself
  element.style.backgroundColor = "rgba(239, 68, 68, 0.2)";
  element.style.border = "1px solid rgba(239, 68, 68, 0.5)";
  element.style.borderRadius = "4px";
  element.style.padding = "2px";
}

function processNode(node) {
  if (scannedNodes.has(node)) return;
  scannedNodes.add(node);

  const text = node.innerText || node.textContent;
  if (!text || text.length < 20) return; // Ignore short texts like "Hello", "Ok"

  // Quick offline filter to avoid hitting backend for every single chat message
  const triggerWords = ["return", "profit", "guaranteed", "sure shot", "jackpot", "tips", "calls", "telegram", "vip", "premium", "accuracy"];
  const lowerText = text.toLowerCase();
  
  const hasTrigger = triggerWords.some(word => lowerText.includes(word));
  if (!hasTrigger) return; // Skip safe casual messages

  // Send to backend via background script
  chrome.runtime.sendMessage({ action: "SCAN_TEXT", text: text }, (response) => {
    if (response && response.success) {
      if (response.data.is_sebi_violation) {
        injectBadge(node, response.data);
      }
    }
  });
}

// Observe DOM for new messages
const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.type === "childList") {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) {
          
          // WhatsApp uses span.selectable-text for chat bubbles
          // Telegram uses .message for chat bubbles
          const messageElements = node.querySelectorAll ? 
            node.querySelectorAll('span.selectable-text, .message, div[dir="ltr"]') : [];
            
          messageElements.forEach(processNode);

          // Check the node itself in case it IS the message element
          if (node.matches && node.matches('span.selectable-text, .message, div[dir="ltr"]')) {
            processNode(node);
          }
        }
      });
    }
  }
});

// Start observing
observer.observe(document.body, {
  childList: true,
  subtree: true
});

console.log("🛡️ FraudShield SEBI Live Extension Active!");
