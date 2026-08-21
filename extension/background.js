chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SCAN_TEXT") {
    fetch("http://127.0.0.1:8000/api/scan-text", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: request.text,
        advisor_reg_no: ""
      })
    })
    .then(response => response.json())
    .then(data => {
      sendResponse({ success: true, data: data });
    })
    .catch(error => {
      console.error("FraudShield Backend Error:", error);
      sendResponse({ success: false, error: error.message });
    });
    
    // Return true to indicate asynchronous response
    return true;
  }
});
