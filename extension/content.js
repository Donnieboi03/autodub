/**
 * AutoDub overlay content script.
 * - Prefetch EN chunks keyed by cue text (caption-faithful)
 * - Play on cue start (± nudge)
 * - Center-suppress / duck via Web Audio when MediaElementSource works
 * Emits: overlay_underrun, audio_tap_unavailable
 */
(() => {
  if (window.__autodubOverlayInstalled) return;
  window.__autodubOverlayInstalled = true;

  const STATE = {
    enabled: false,
    nudgeMs: 0,
    duckGain: 0.2,
    chunkBase: "",
    manifest: null,
    byText: new Map(),
    audioCtx: null,
    videoGain: null,
    enGain: null,
    tapOk: false,
    activeCueKey: null,
    playing: null,
  };

  function emit(name, payload = {}) {
    console.info("[autodub]", name, payload);
    window.dispatchEvent(new CustomEvent("autodub-event", { detail: { name, ...payload } }));
  }

  function normalize(text) {
    return String(text || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cueKey(text, start) {
    return `${normalize(text)}|${Number(start).toFixed(3)}`;
  }

  async function loadManifest(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`manifest ${r.status}`);
    const data = await r.json();
    STATE.manifest = data;
    STATE.byText.clear();
    for (const line of data.lines || []) {
      const key = cueKey(line.source_caption || line.text, line.start_s);
      STATE.byText.set(key, line);
      STATE.byText.set(normalize(line.text), line);
    }
    return data;
  }

  function findVideo() {
    return document.querySelector("video");
  }

  function setupAudioTap(video) {
    if (STATE.audioCtx) return STATE.tapOk;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      const src = ctx.createMediaElementSource(video);
      const vg = ctx.createGain();
      const eg = ctx.createGain();
      vg.gain.value = 1.0;
      eg.gain.value = 1.0;
      src.connect(vg);
      vg.connect(ctx.destination);
      eg.connect(ctx.destination);
      STATE.audioCtx = ctx;
      STATE.videoGain = vg;
      STATE.enGain = eg;
      STATE.tapOk = true;
      return true;
    } catch (err) {
      STATE.tapOk = false;
      emit("audio_tap_unavailable", { reason: String(err && err.message) });
      return false;
    }
  }

  function duck(on) {
    if (!STATE.tapOk || !STATE.videoGain) return;
    STATE.videoGain.gain.setTargetAtTime(
      on ? STATE.duckGain : 1.0,
      STATE.audioCtx.currentTime,
      0.03
    );
  }

  function chunkUrl(line) {
    if (line.audio_url) return line.audio_url;
    if (line.chunk) return new URL(line.chunk, STATE.chunkBase || location.href).href;
    if (line.audio) {
      // file:// local manifest may point at absolute paths — not fetchable from page;
      // prefer relative chunk names under extension fixture.
      const name = String(line.audio).split("/").pop();
      return new URL(`chunks/${name}`, STATE.chunkBase || location.href).href;
    }
    return null;
  }

  const prefetchCache = new Map();

  async function prefetchLine(line) {
    const url = chunkUrl(line);
    if (!url) return null;
    if (prefetchCache.has(url)) return prefetchCache.get(url);
    const p = fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`chunk ${r.status}`);
        return r.arrayBuffer();
      })
      .then((buf) => {
        const blob = new Blob([buf], { type: "audio/mpeg" });
        return URL.createObjectURL(blob);
      })
      .catch((err) => {
        prefetchCache.delete(url);
        throw err;
      });
    prefetchCache.set(url, p);
    return p;
  }

  async function prefetchAll() {
    const lines = (STATE.manifest && STATE.manifest.lines) || [];
    await Promise.allSettled(lines.map((l) => prefetchLine(l)));
  }

  async function playLine(line, video) {
    let objectUrl;
    try {
      objectUrl = await prefetchLine(line);
    } catch (err) {
      emit("overlay_underrun", { index: line.index, reason: String(err && err.message) });
      return;
    }
    if (!objectUrl) {
      emit("overlay_underrun", { index: line.index, reason: "no_chunk" });
      return;
    }
    if (STATE.playing) {
      try {
        STATE.playing.pause();
      } catch (_) {}
    }
    const audio = new Audio(objectUrl);
    STATE.playing = audio;
    if (STATE.tapOk && STATE.audioCtx) {
      try {
        await STATE.audioCtx.resume();
      } catch (_) {}
    }
    duck(true);
    const startAt = performance.now();
    await new Promise((resolve) => {
      audio.onended = () => {
        duck(false);
        resolve();
      };
      audio.onerror = () => {
        emit("overlay_underrun", { index: line.index, reason: "play_error" });
        duck(false);
        resolve();
      };
      const p = audio.play();
      if (p && p.catch) p.catch(() => resolve());
      const lag = performance.now() - startAt;
      if (lag > 150) {
        emit("overlay_underrun", { index: line.index, lag_ms: Math.round(lag) });
      }
    });
  }

  function attachTracks(video) {
    const tracks = Array.from(video.textTracks || []);
    for (const track of tracks) {
      track.mode = track.mode === "disabled" ? "hidden" : track.mode;
      track.addEventListener("cuechange", () => onCueChange(video, track));
    }
    // also poll currentTime for fixture pages with delayed track load
    video.addEventListener("timeupdate", () => onTimeUpdate(video));
  }

  function matchLine(video) {
    const t = video.currentTime + STATE.nudgeMs / 1000;
    const tracks = Array.from(video.textTracks || []);
    for (const track of tracks) {
      const cues = track.activeCues;
      if (!cues || !cues.length) continue;
      const cue = cues[0];
      const text = normalize(cue.text);
      const key = cueKey(cue.text, cue.startTime);
      let line = STATE.byText.get(key) || STATE.byText.get(text);
      if (!line && STATE.manifest) {
        line = (STATE.manifest.lines || []).find(
          (l) => t >= l.start_s - 0.05 && t < l.end_s + 0.05 && normalize(l.text) === text
        );
      }
      if (line) return { line, key };
    }
    return null;
  }

  function onCueChange(video) {
    if (!STATE.enabled) return;
    const hit = matchLine(video);
    if (!hit) return;
    if (hit.key === STATE.activeCueKey) return;
    STATE.activeCueKey = hit.key;
    playLine(hit.line, video);
  }

  let lastPollKey = null;
  function onTimeUpdate(video) {
    if (!STATE.enabled) return;
    const hit = matchLine(video);
    if (!hit) {
      lastPollKey = null;
      return;
    }
    if (hit.key === lastPollKey || hit.key === STATE.activeCueKey) return;
    lastPollKey = hit.key;
    STATE.activeCueKey = hit.key;
    playLine(hit.line, video);
  }

  async function start(opts = {}) {
    const video = findVideo();
    if (!video) throw new Error("no <video> on page");
    STATE.enabled = true;
    STATE.nudgeMs = Number(opts.nudgeMs || 0);
    STATE.duckGain = Number(opts.duckGain ?? 0.2);
    STATE.chunkBase = opts.chunkBase || location.href;
    if (opts.manifestUrl) await loadManifest(opts.manifestUrl);
    setupAudioTap(video);
    attachTracks(video);
    await prefetchAll();
    emit("overlay_ready", { tap: STATE.tapOk, lines: (STATE.manifest && STATE.manifest.lines || []).length });
  }

  function stop() {
    STATE.enabled = false;
    duck(false);
    if (STATE.playing) {
      try {
        STATE.playing.pause();
      } catch (_) {}
    }
  }

  function probe() {
    const video = findVideo();
    const hasTrack = !!(video && video.textTracks && video.textTracks.length);
    let tap = false;
    if (video) tap = setupAudioTap(video);
    return {
      video: !!video,
      textTrack: hasTrack,
      audioTap: tap,
      events: ["line_rendered", "cast_matched", "cache_hit", "overlay_underrun", "audio_tap_unavailable"],
    };
  }

  window.AutoDubOverlay = { start, stop, loadManifest, prefetchAll, probe, emit };
  emit("content_script_ready", {});
})();
