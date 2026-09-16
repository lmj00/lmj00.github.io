/* Scope both height messages and reading controls to generated article scenes. */
(() => {
  "use strict";
  // Generation accepts up to 1050px of content; leave room for the runtime's
  // resize padding. This cap is also exercised by the browser regression tests.
  const MAX_FRAME_HEIGHT = 1100;
  const frames = [...document.querySelectorAll("iframe.ai-scene-frame")];
  // A cached frame may send its first measurement before this deferred script.
  // Measure both already-loaded frames and frames that finish loading later.
  frames.forEach(frame => {
    const measure = () => frame.contentWindow?.postMessage({type: "article-scene:measure"}, "*");
    frame.addEventListener("load", measure);
    measure();
  });
  window.addEventListener("message", event => {
    if (event.origin !== "null" || !event.data || event.data.type !== "article-scene:resize") return;
    const frame = frames.find(item => item.contentWindow === event.source);
    const height = event.data.height;
    if (!frame || typeof height !== "number" || !Number.isFinite(height)) return;
    const nextHeight = `${Math.max(160, Math.min(MAX_FRAME_HEIGHT, Math.ceil(height)))}px`;
    if (frame.style.height !== nextHeight) frame.style.height = nextHeight;
  });
})();
