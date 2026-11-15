const statusEl = document.getElementById("status");

function setStatus(msg) {
  statusEl.textContent = typeof msg === "string" ? msg : JSON.stringify(msg, null, 2);
}

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function injectAndCall(fnName, args = []) {
  const tab = await activeTab();
  if (!tab || tab.id == null) throw new Error("no active tab");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (name, callArgs) => {
      if (!window.AutoDubOverlay) return { error: "content script not loaded" };
      const fn = window.AutoDubOverlay[name];
      if (!fn) return { error: `missing ${name}` };
      return Promise.resolve(fn(...callArgs));
    },
    args: [fnName, args],
  });
  return result;
}

document.getElementById("probe").addEventListener("click", async () => {
  try {
    // content script may already be present; probe via execute if scripting allowed
    const tab = await activeTab();
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => (window.AutoDubOverlay ? window.AutoDubOverlay.probe() : { error: "no overlay" }),
    });
    setStatus(result);
  } catch (err) {
    setStatus(String(err.message || err));
  }
});

document.getElementById("start").addEventListener("click", async () => {
  const manifestUrl = document.getElementById("manifest").value.trim();
  const nudgeMs = Number(document.getElementById("nudge").value || 0);
  try {
    const tab = await activeTab();
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: async (manifestUrl, nudgeMs) => {
        if (!window.AutoDubOverlay) return { error: "content script not loaded — open fixture.html" };
        await window.AutoDubOverlay.start({ manifestUrl, nudgeMs });
        return window.AutoDubOverlay.probe();
      },
      args: [manifestUrl, nudgeMs],
    });
    setStatus(result);
  } catch (err) {
    setStatus(String(err.message || err));
  }
});

document.getElementById("stop").addEventListener("click", async () => {
  try {
    const tab = await activeTab();
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.AutoDubOverlay && window.AutoDubOverlay.stop(),
    });
    setStatus("stopped");
  } catch (err) {
    setStatus(String(err.message || err));
  }
});
