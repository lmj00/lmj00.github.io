/* Trusted finite-state player. Models supply data/HTML/CSS, never executable JS. */
(() => {
  "use strict";
  const scene = JSON.parse(document.getElementById("scene-data").textContent);
  const states = new Map(scene.states.map(state => [state.id, state]));
  const transitions = new Map((scene.transitions || []).map(edge => [`${edge.from}->${edge.to}`, edge]));
  const stateEffects = new Map((scene.effects || []).map(edge => [`${edge.from}->${edge.to}`, edge]));
  const changeExplanations = new Map((scene.change_explanations || []).map(edge => [`${edge.from}->${edge.to}`, edge]));
  const content = document.getElementById("scene-content");
  const controls = document.getElementById("scene-controls");
  const status = document.getElementById("scene-status");
  const transitionStatus = document.getElementById("scene-transition-status");
  const scenarioControls = document.getElementById("scene-scenarios");
  const previous = document.getElementById("scene-previous");
  const next = document.getElementById("scene-next");
  const diagram = scene.presentation ? window.ArticleDiagram : null;
  const playback = scene.playback || {steps: [], interval_ms: 3000};
  const play = document.getElementById("scene-play");
  const progress = document.getElementById("scene-progress");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const manualDefault = ["compare", "explore"].includes(scene.interaction_mode);
  const initialActions = states.get(scene.initial).actions;
  // A one-edge choice already describes an executable action. Display it once,
  // rather than asking the reader to select a route and then repeat the action.
  const directScenarios = new Map((scene.scenarios || []).filter(option =>
    option.steps.length === 2 && option.steps[0] === scene.initial &&
    initialActions.filter(action => action.target === option.steps[1]).length === 1
  ).map(option => [option.id, option]));
  let route = playback.steps;
  let selectedScenario = (scene.scenarios || []).find(option => JSON.stringify(option.steps) === JSON.stringify(route))?.id || "";
  let timer = null;
  let position = 0;
  let automaticUsed = false;
  let visible = false;
  let intent = "idle"; // User intent survives offscreen/tab suspension.
  let resumeIntent = "playing";
  let remaining = playback.interval_ms;
  let due = 0;
  let effects = [];
  let history = [];
  let motion = null;
  let frame = null;
  let changeSummary = document.getElementById("scene-change-summary");
  let changeSlot = null;
  let extraDetails = null;
  let extraToggle = null;
  if (changeExplanations.size && !changeSummary) {
    changeSummary = document.createElement("section");
    changeSummary.id = "scene-change-summary";
    changeSummary.className = "scene-change-summary";
    changeSummary.setAttribute("aria-label", "변경 전후 비교");
    changeSummary.tabIndex = -1;
    changeSummary.hidden = true;
    content.after(changeSummary);
  }
  if (changeSummary) {
    changeSlot = document.createElement("div");
    changeSlot.className = "scene-change-slot";
    changeSlot.style.display = "flow-root"; // Contain the ledger's margins while sizing.
    changeSummary.before(changeSlot);
    changeSlot.append(changeSummary);
  }
  if (changeExplanations.size) {
    extraDetails = document.createElement("details");
    extraDetails.id = "scene-extra-details";
    extraDetails.style.display = "flow-root";
    extraToggle = document.createElement("summary");
    extraToggle.textContent = "추가 설명";
    status.before(extraDetails);
    extraDetails.append(extraToggle, status);
    extraDetails.addEventListener("toggle", resize);
  }

  function focusExplanation() {
    (changeSummary && !changeSummary.hidden ? changeSummary : status)?.focus({preventScroll: true});
  }

  function primaryChange(changes) {
    // Prefer an observable value change over filling an empty name/type label.
    // No field names or domain vocabulary are interpreted here. Equal scores
    // retain the author's order; this is presentation, not a semantic verdict.
    const placeholder = value => !value.trim() || /^[\s\-—–−·.⋯…]+$/u.test(value);
    const numeric = value => /(^|[:=]\s*)[+\-−]?\p{N}/u.test(value.trim());
    const score = change => {
      const before = !placeholder(change.before), after = !placeholder(change.after);
      return (before && after ? 4 : 0) + (after ? 1 : 0) +
        (after && numeric(change.after) && (!before || numeric(change.before)) ? 1 : 0);
    };
    return changes.reduce((best, change) => score(change) > score(best) ? change : best);
  }

  function fillChange(panel, explanation) {
    panel.replaceChildren();
    panel.hidden = !explanation;
    if (!explanation) return;
    panel.dataset.from = explanation.from;
    panel.dataset.to = explanation.to;
    function text(tag, className, value) {
      const node = document.createElement(tag);
      node.className = className;
      node.textContent = value; // Validated plain data, never executable markup.
      return node;
    }
    const primary = primaryChange(explanation.changes);
    const secondary = explanation.changes.filter(change => change !== primary);
    function changeRow(change) {
      const row = text("div", "scene-change-row", "");
      row.dataset.entity = change.entity;
      row.dataset.primary = String(change === primary);
      if ([change.before, change.after].some(value => value.length > 70 || value.includes("\n"))) row.dataset.layout = "stacked";
      const before = text("span", "scene-change-before", change.before);
      before.setAttribute("aria-label", `변경 전: ${change.before}`);
      const after = text("span", "scene-change-after", change.after);
      after.setAttribute("aria-label", `변경 후: ${change.after}`);
      const arrow = text("span", "scene-change-arrow", "→");
      arrow.setAttribute("aria-hidden", "true");
      row.append(text("span", "scene-change-label", change.label), before, arrow, after);
      return row;
    }
    panel.append(text("h3", "scene-change-heading", "변경 전 → 변경 후"), changeRow(primary));
    panel.append(text("p", "scene-change-reason", explanation.reason));
    const invariants = text("div", "scene-change-invariants", "");
    explanation.invariants.forEach(invariant => {
      const row = text("div", "scene-change-invariant", "");
      row.dataset.entity = invariant.entity;
      row.append(text("span", "scene-change-invariant-label", `${invariant.label} · 유지`),
        text("span", "scene-change-invariant-value", invariant.value));
      invariants.append(row);
    });
    if (invariants.childElementCount) panel.append(invariants);
    if (secondary.length) {
      // Every exact evidence value remains in the DOM. Native disclosure keeps
      // the extra comparisons keyboard-accessible without repeating all rows
      // on first reading; a new result starts closed, never inherits stale UI.
      const details = text("details", "scene-change-details", "");
      details.append(text("summary", "scene-change-details-toggle", `추가 변경 ${secondary.length}개`));
      secondary.forEach(change => details.append(changeRow(change)));
      details.addEventListener("toggle", resize);
      panel.append(details);
    }
  }

  function showChange(from, to) {
    if (!changeSummary) return;
    const explanation = changeExplanations.get(`${from}->${to}`);
    fillChange(changeSummary, explanation);
    content.querySelectorAll("[data-scene-changed]").forEach(node => delete node.dataset.sceneChanged);
    (explanation?.changes || []).forEach(change => {
      [...content.querySelectorAll("[data-entity]")].find(node => node.dataset.entity === change.entity)?.setAttribute("data-scene-changed", "true");
    });
  }

  function measureChange(explanation) {
    if (!changeSlot || !explanation) return 0;
    const probe = document.createElement("div");
    probe.className = "scene-change-slot";
    probe.setAttribute("aria-hidden", "true");
    probe.inert = true;
    Object.assign(probe.style, {display:"flow-root", position:"absolute", visibility:"hidden", left:"-10000px",
      width:`${changeSlot.getBoundingClientRect().width}px`, pointerEvents:"none"});
    const panel = document.createElement("section");
    panel.className = "scene-change-summary";
    fillChange(panel, explanation);
    probe.append(panel);
    document.body.append(probe);
    const height = probe.getBoundingClientRect().height;
    probe.remove();
    return height;
  }

  function measureExtra(explanation, description) {
    if (!extraDetails || !explanation ||
        explanation.reason.trim().replace(/\s+/g, " ") === description.trim().replace(/\s+/g, " ")) return 0;
    // Measure the trusted disclosure at this width without exposing a future
    // result. Restore its current state synchronously, before a browser paint.
    const saved = {hidden:extraDetails.hidden, open:extraDetails.open, toggle:extraToggle.hidden};
    extraDetails.hidden = false;
    extraDetails.open = false;
    extraToggle.hidden = false;
    const height = extraDetails.getBoundingClientRect().height;
    extraDetails.hidden = saved.hidden;
    extraDetails.open = saved.open;
    extraToggle.hidden = saved.toggle;
    return height;
  }

  function syncScenario() {
    if (history.length < 2) {
      if (directScenarios.has(selectedScenario)) selectedScenario = "";
      return;
    }
    const matching = (scene.scenarios || []).filter(option => history.every((id, index) => option.steps[index] === id));
    if (matching.length === 1) {
      selectedScenario = matching[0].id;
      route = matching[0].steps;
    } else if (!matching.some(option => option.id === selectedScenario)) selectedScenario = "";
  }

  function running() { return intent === "playing" || intent === "manual"; }
  function canMove() { return running() && visible && !document.hidden; }
  function revealStage() {
    // An explicit command below a tall mobile scene can leave its stage
    // outside the viewport. The browser scrolls the iframe's ancestors too;
    // no privileged parent access or model-supplied coordinates are needed.
    if (!visible && !document.hidden) {
      content.scrollIntoView({block: "center", inline: "nearest", behavior: "instant"});
    }
  }
  function cancelEffects() {
    effects.forEach(effect => effect.cancel());
    effects = [];
  }
  let resizeFrame = null;
  let lastHeight = null;
  function resize(force = false) {
    // Coalesce layout/observer events. Measurements are still of the real
    // document, never a smaller synthetic height that could hide content.
    if (force === true) lastHeight = null;
    if (resizeFrame !== null) return;
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = null;
      const height = document.body.scrollHeight + 12;
      if (height === lastHeight) return;
      lastHeight = height;
      parent.postMessage({type: "article-scene:resize", height}, "*");
    });
  }
  window.addEventListener("message", event => {
    if (event.source === parent && event.data?.type === "article-scene:measure") resize(true);
  });
  function updatePlayback() {
    content.dataset.playback = running() && timer === null && frame === null ? "suspended" : intent;
    // Manual-only scenes still need an accessible pause/resume control while
    // a transfer is in flight, even when they have no automatic route.
    document.getElementById("scene-playback").hidden = route.length < 2 && !motion;
    const completed = route.length > 1 && position === route.length - 1 && !motion;
    const selectedResult = manualDefault && intent === "paused" && resumeIntent === "manual" && !motion && history.length > 1;
    play.textContent = running() ? "일시정지" : selectedResult ? "선택한 경로 재생" : completed ? "다시 재생" : intent === "paused" ? "계속 재생" : manualDefault ? "경로 재생" : "자동 재생";
    play.setAttribute("aria-pressed", String(running()));
    status.setAttribute("aria-live", running() ? "off" : "polite");
    changeSummary?.setAttribute("aria-live", running() ? "off" : "polite");
    progress.textContent = motion?.comparisonOrigin ? "같은 원본 · 결과 비교 중" : selectedResult ? "직접 선택한 결과" : position >= 0 && route.length ? `${position + 1} / ${route.length}${completed ? " · 재생 완료" : motion ? (motion.effect ? " · 변화 중" : " · 전달 중") : ""}` : "직접 탐색 중";
    if (previous) {
      previous.hidden = scene.states.length < 2;
      previous.disabled = !motion && history.length < 2;
    }
    controls.querySelectorAll("button").forEach(button => { button.disabled = Boolean(motion); });
    if (next) next.disabled = Boolean(motion) || position < 0 || position >= route.length - 1;
    if (scenarioControls) scenarioControls.querySelectorAll("button").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.scenario === selectedScenario));
      const option = directScenarios.get(button.dataset.scenario);
      button.disabled = Boolean(motion && option);
      const index = option && content.dataset.state === scene.initial ? initialActions.findIndex(action => action.target === option.steps[1]) : -1;
      if (index >= 0) button.dataset.action = String(index);
      else delete button.dataset.action;
    });
  }

  function suspend() {
    if (timer !== null) remaining = Math.max(0, due - performance.now());
    clearTimeout(timer);
    timer = null;
    if (motion && frame !== null) {
      motion.elapsed += Math.max(0, performance.now() - motion.started);
      cancelAnimationFrame(frame);
      frame = null;
    }
    effects.forEach(effect => { if (effect.playState === "running") effect.pause(); });
    updatePlayback();
  }
  function pause() {
    if (running()) resumeIntent = intent;
    suspend();
    intent = "paused";
    updatePlayback();
  }
  function clearMotion() {
    cancelAnimationFrame(frame);
    frame = null;
    if (motion) {
      (motion.animations || []).forEach(animation => animation.cancel());
      motion.layer.remove();
      motion = null;
    }
    content.dataset.phase = "settled";
    delete content.dataset.transition;
    delete content.dataset.step;
    delete content.dataset.effect;
    delete content.dataset.effectProgress;
    delete content.dataset.comparisonOrigin;
    changeSummary?.removeAttribute("aria-busy");
    if (changeSummary) changeSummary.inert = false;
    if (extraDetails) extraDetails.inert = false;
    if (transitionStatus) {
      transitionStatus.textContent = "";
      transitionStatus.hidden = true;
    }
  }
  function cancelPending() {
    clearTimeout(timer);
    timer = null;
    clearMotion();
    cancelEffects();
    remaining = playback.interval_ms;
  }

  // Keep existing entity elements alive while reconciling a validated snapshot.
  // Wrapper/text changes are allowed, but a stable data-entity is not replaced
  // simply because the model supplied another complete HTML snapshot.
  function reconcile(html) {
    const template = document.createElement("template");
    template.innerHTML = html; // Allowlisted and normalized during generation.
    const keyed = new Map([...content.querySelectorAll("[data-entity]")].map(node => [node.dataset.entity, node]));
    function children(parentNode, incomingParent) {
      let cursor = parentNode.firstChild;
      [...incomingParent.childNodes].forEach(incoming => {
        const key = incoming.nodeType === Node.ELEMENT_NODE ? incoming.dataset.entity : undefined;
        let node = key ? keyed.get(key) : cursor;
        if (!node || node.nodeType !== incoming.nodeType || node.nodeName !== incoming.nodeName ||
            (node.nodeType === Node.ELEMENT_NODE && ((!key && node.dataset.entity) || node.contains(parentNode)))) {
          node = incoming.cloneNode(false);
        }
        if (node !== cursor) parentNode.insertBefore(node, cursor);
        if (incoming.nodeType === Node.ELEMENT_NODE) {
          [...node.attributes].forEach(attribute => {
            if (!incoming.hasAttribute(attribute.name)) node.removeAttribute(attribute.name);
          });
          [...incoming.attributes].forEach(attribute => node.setAttribute(attribute.name, attribute.value));
          children(node, incoming);
        } else if (node.nodeValue !== incoming.nodeValue) node.nodeValue = incoming.nodeValue;
        cursor = node.nextSibling;
      });
      while (cursor) {
        const next = cursor.nextSibling;
        cursor.remove();
        cursor = next;
      }
    }
    children(content, template.content);
  }

  function show(id, animate = false, record = true, explanationFrom = null) {
    const state = states.get(id);
    if (!state) return;
    const from = content.dataset.state;
    cancelEffects();
    const origin = content.getBoundingClientRect();
    const before = new Map([...content.querySelectorAll("[data-entity]")].map(node => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return [node.dataset.entity, {x: rect.x - origin.x, y: rect.y - origin.y,
        text: node.textContent, appearance: [style.color, style.backgroundColor, style.borderColor].join("|")}];
    }));
    reconcile(state.html);
    if (diagram) diagram.draw(content, scene);
    else window.ArticleDiagram?.icons(content);
    window.ArticleCharts?.draw(content, scene, id);
    content.dataset.state = id;
    content.dataset.phase = "settled";
    if (record && history[history.length - 1] !== id) history.push(id);
    syncScenario();
    showChange(explanationFrom || (record ? from : history[history.length - 2]), id);
    if (animate && !reduced.matches && visible && !document.hidden) {
      const nextOrigin = content.getBoundingClientRect();
      content.querySelectorAll("[data-entity]").forEach(node => {
        const saved = before.get(node.dataset.entity);
        if (!saved) return;
        const rect = node.getBoundingClientRect();
        const dx = saved.x - (rect.x - nextOrigin.x);
        const dy = saved.y - (rect.y - nextOrigin.y);
        const style = getComputedStyle(node);
        if (Math.abs(dx) + Math.abs(dy) > 2) {
          effects.push(node.animate([
            {translate: `${dx}px ${dy}px`}, {translate: "0px 0px"}
          ], {duration: 650, easing: "ease-in-out"}));
        } else if (!diagram && !changeExplanations.size && (saved.text !== node.textContent || saved.appearance !== [style.color, style.backgroundColor, style.borderColor].join("|"))) {
          effects.push(node.animate([
            {outline: "2px solid #79b8ff", outlineOffset: "3px"},
            {outline: "2px solid transparent", outlineOffset: "3px"}
          ], {duration: 900}));
        }
      });
      // Legacy scenes without identities retain their restrained fade.
      if (!before.size) effects.push(content.animate([{opacity: 0.35}, {opacity: 1}], {duration: 240}));
    }
    status.textContent = state.description;
    const normalize = value => value.trim().replace(/\s+/g, " ");
    const hasChange = changeSummary && !changeSummary.hidden;
    status.hidden = Boolean(hasChange &&
      normalize(changeSummary.querySelector(".scene-change-reason").textContent) === normalize(state.description));
    if (extraDetails) {
      // Distinct descriptions remain available without guessing whether they
      // repeat the reason. A new choice always starts with a compact summary.
      extraDetails.hidden = status.hidden;
      extraToggle.hidden = !hasChange;
      extraDetails.open = !hasChange;
    }
    controls.replaceChildren();
    state.actions.forEach((action, index) => {
      if (id === scene.initial && [...directScenarios.values()].some(option => option.steps[1] === action.target)) return;
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = action.label;
      button.dataset.action = String(index);
      button.addEventListener("click", () => {
        if (motion) return;
        act(action.target);
      });
      controls.append(button);
    });
    position = route.indexOf(id);
    updatePlayback();
    resize();
  }

  function act(target, comparisonOrigin = null) {
    if (motion) return;
    automaticUsed = true;
    suspend();
    remaining = playback.interval_ms;
    intent = "manual";
    resumeIntent = "manual";
    if (comparisonOrigin) history = [comparisonOrigin];
    revealStage();
    travel(target, () => {
      intent = "paused";
      updatePlayback();
      focusExplanation();
    }, comparisonOrigin);
  }

  function geometry(step) {
    const anchors = new Map([...content.querySelectorAll("[data-entity]")].map(node => [node.dataset.entity, node]));
    const source = anchors.get(step.source);
    const target = anchors.get(step.target);
    if (!source || !target) return null; // Python validation rejects missing anchors.
    if (diagram) return diagram.geometry(content, source, target);
    const origin = content.getBoundingClientRect();
    const a = source.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const start = {x: a.left + a.width / 2 - origin.left, y: a.top + a.height / 2 - origin.top};
    const end = {x: b.left + b.width / 2 - origin.left, y: b.top + b.height / 2 - origin.top};
    // A shallow arc separates the travelling teaching token from a board's
    // ordinary connecting rule, without inventing a model-controlled path.
    const bend = Math.min(32, Math.hypot(end.x - start.x, end.y - start.y) * 0.12);
    const middle = {x: (start.x + end.x) / 2, y: Math.max(12, (start.y + end.y) / 2 - bend)};
    return {start, middle, end, width: origin.width, height: origin.height};
  }
  function paint(fraction) {
    if (!motion) return;
    if (motion.effect) {
      const t = Math.min(1, Math.max(0, fraction));
      motion.animations.forEach(animation => { animation.currentTime = t * motion.steps[0].duration_ms; });
      content.dataset.effectProgress = t.toFixed(3);
      return;
    }
    const step = motion.steps[motion.index];
    const points = geometry(step);
    if (!points) return;
    const {start, middle, end, width, height} = points;
    motion.wire.setAttribute("viewBox", `0 0 ${width} ${height}`);
    motion.path.setAttribute("d", diagram ? diagram.path(points) : `M${start.x},${start.y} Q${middle.x},${middle.y} ${end.x},${end.y}`);
    const t = Math.min(1, Math.max(0, fraction));
    const {x,y} = diagram ? diagram.point(points,t) : {
      x:(1 - t) ** 2 * start.x + 2 * (1 - t) * t * middle.x + t ** 2 * end.x,
      y:(1 - t) ** 2 * start.y + 2 * (1 - t) * t * middle.y + t ** 2 * end.y
    };
    // Keep the label readable inside a narrow iframe at both endpoints.
    const tokenBounds = motion.token.getBoundingClientRect();
    const half = tokenBounds.width / 2;
    const halfHeight = tokenBounds.height / 2;
    motion.token.style.left = `${Math.max(half + 4, Math.min(width - half - 4, x))}px`;
    motion.token.style.top = `${Math.max(halfHeight + 4, Math.min(height - halfHeight - 4, y))}px`;
    motion.token.dataset.progress = t.toFixed(3);
  }
  function prepareStep() {
    const step = motion.steps[motion.index];
    motion.token.textContent = step.label;
    motion.token.dataset.source = step.source;
    motion.token.dataset.target = step.target;
    motion.token.dataset.step = String(motion.index);
    motion.token.dataset.kind = step.kind || "message";
    motion.wire.dataset.kind = step.kind || "message";
    content.dataset.step = String(motion.index);
    if (transitionStatus) {
      transitionStatus.hidden = false;
      transitionStatus.textContent = `${motion.index + 1} / ${motion.steps.length} · ${step.label}`;
    }
    paint(0);
  }
  function completeMotion() {
    if (!motion) return;
    const {target, done, effect, comparisonOrigin} = motion;
    clearMotion();
    show(target, !effect, true, comparisonOrigin);
    done();
  }
  function tick(now) {
    frame = null;
    if (!motion) return;
    if (!canMove()) { motion.elapsed += Math.max(0, now - motion.started); updatePlayback(); return; }
    let elapsed = motion.elapsed + Math.max(0, now - motion.started);
    let step = motion.steps[motion.index];
    // Carry over frame rounding instead of adding one frame per sequence step.
    while (elapsed >= step.duration_ms) {
      elapsed -= step.duration_ms;
      motion.index += 1;
      if (motion.index >= motion.steps.length) { completeMotion(); return; }
      motion.elapsed = elapsed;
      motion.started = now;
      prepareStep();
      step = motion.steps[motion.index];
    }
    paint(elapsed / step.duration_ms);
    frame = requestAnimationFrame(tick);
  }
  function resumeMotion() {
    if (!motion || frame !== null || !canMove()) { updatePlayback(); return; }
    motion.started = performance.now();
    frame = requestAnimationFrame(tick);
    updatePlayback();
  }
  function changeValues(target, effect, done, comparisonOrigin = null) {
    cancelEffects();
    const from = content.dataset.state;
    const origin = content.getBoundingClientRect();
    const changeHeight = changeSlot?.getBoundingClientRect().height || 0;
    const explanation = changeExplanations.get(`${comparisonOrigin || from}->${target}`);
    const nextChangeHeight = measureChange(explanation);
    if (changeSummary) changeSummary.inert = true;
    const extraHeight = extraDetails?.getBoundingClientRect().height || 0;
    const extraWasHidden = extraDetails?.hidden;
    const nextExtraHeight = measureExtra(explanation, states.get(target).description);
    const animatedEntities = new Set(effect.entities);
    if (comparisonOrigin) {
      // Switching alternatives can also undo a field changed by the old choice.
      // Fade those verified field identities too, but never animate unchanged data.
      const oldEffect = stateEffects.get(`${comparisonOrigin}->${from}`);
      (oldEffect?.entities || []).forEach(entity => animatedEntities.add(entity));
      const incoming = document.createElement("template");
      incoming.innerHTML = states.get(target).html;
      const nextText = new Map([...incoming.content.querySelectorAll("[data-entity]")].map(node => [node.dataset.entity, node.textContent]));
      content.querySelectorAll("[data-entity]").forEach(node => {
        if (node.textContent === nextText.get(node.dataset.entity)) animatedEntities.delete(node.dataset.entity);
      });
    }
    const old = new Map([...content.querySelectorAll("[data-entity]")].map(node => {
      const rect = node.getBoundingClientRect();
      let snapshot = null;
      if (animatedEntities.has(node.dataset.entity)) {
        snapshot = node.cloneNode(true);
        // Preserve appearance without retaining tracking IDs or duplicating
        // live context. All markup was sanitized; this copy is inert/aria-hidden.
        const originals = [node, ...node.querySelectorAll("*")];
        [snapshot, ...snapshot.querySelectorAll("*")].forEach((clone, index) => {
          const style = getComputedStyle(originals[index]);
          [...style].forEach(key => clone.style.setProperty(key, style.getPropertyValue(key)));
          clone.removeAttribute("data-entity");
          clone.removeAttribute("id");
        });
      }
      return [node.dataset.entity, {rect, snapshot}];
    }));
    reconcile(states.get(target).html);
    if (diagram) diagram.draw(content, scene);
    else window.ArticleDiagram?.icons(content);
    window.ArticleCharts?.draw(content, scene, target);
    const layer = document.createElement("div");
    layer.className = "scene-effect-layer";
    layer.setAttribute("aria-hidden", "true");
    Object.assign(layer.style, {position:"absolute", inset:"0", pointerEvents:"none", zIndex:"10"});
    const animations = [];
    function animate(node, frames) {
      const animation = node.animate(frames, {duration:effect.duration_ms, easing:"cubic-bezier(.22,.7,.2,1)", fill:"both"});
      animation.pause();
      animation.currentTime = 0;
      animations.push(animation);
    }
    const nextOrigin = content.getBoundingClientRect();
    if (changeSlot && Math.abs(changeHeight - nextChangeHeight) > 1) {
      animate(changeSlot, [{height:`${changeHeight}px`, overflow:"hidden"},
        {height:`${nextChangeHeight}px`, overflow:"hidden"}]);
    }
    if (extraDetails && explanation && (!extraWasHidden || nextExtraHeight)) {
      extraDetails.inert = true;
      if (extraWasHidden) {
        extraDetails.hidden = false;
        extraDetails.open = false;
        extraToggle.hidden = false;
      }
      animate(extraDetails, [
        {height:`${extraHeight}px`, overflow:"hidden", marginTop:extraWasHidden ? "0px" : getComputedStyle(extraDetails).marginTop},
        {height:`${nextExtraHeight}px`, overflow:"hidden", marginTop:nextExtraHeight ? "12px" : "0px"}
      ]);
    }
    if (changeSlot && effect.kind !== "reveal" && Math.abs(origin.height - nextOrigin.height) > 1) {
      animate(content, [{height:`${origin.height}px`}, {height:`${nextOrigin.height}px`}]);
    }
    content.querySelectorAll("[data-entity]").forEach(node => {
      const saved = old.get(node.dataset.entity);
      if (!saved) return;
      const rect = node.getBoundingClientRect();
      const dx = saved.rect.x - origin.x - (rect.x - nextOrigin.x);
      const dy = saved.rect.y - origin.y - (rect.y - nextOrigin.y);
      if (animatedEntities.has(node.dataset.entity)) {
        const snapshot = saved.snapshot;
        Object.assign(snapshot.style, {position:"absolute", margin:"0", left:`${saved.rect.x-origin.x}px`,
          top:`${saved.rect.y-origin.y}px`, width:`${saved.rect.width}px`, height:`${saved.rect.height}px`,
          pointerEvents:"none", transform:"none", translate:"none"});
        layer.append(snapshot);
        if (effect.kind === "reveal") {
          animate(node, [
            {height:`${saved.rect.height}px`, overflow:"hidden", opacity:.15},
            {height:`${rect.height}px`, overflow:"hidden", opacity:1}
          ]);
          animate(snapshot, [{opacity:1}, {opacity:0, offset:.6}, {opacity:0}]);
        } else {
          const shift = effect.kind === "transform" ? 14 : 5;
          // A valid layout may meet the stage edge exactly. Keep trusted motion
          // inside that stage instead of requiring generated padding to mask it.
          const left = rect.left - nextOrigin.left, top = rect.top - nextOrigin.top;
          const insetX = Math.max(-left, Math.min(nextOrigin.width - left - rect.width, dx));
          const insetY = Math.max(-top, Math.min(nextOrigin.height - top - rect.height, dy + shift));
          const outgoingY = Math.min(shift, Math.max(0, saved.rect.top - origin.top));
          animate(node, [
            {translate:`${insetX}px ${insetY}px`, scale:effect.kind === "transform" ? ".97" : "1", opacity:0},
            {translate:"0px 0px", scale:"1", opacity:1}
          ]);
          animate(snapshot, [{translate:"0px 0px", opacity:1}, {translate:`0px -${outgoingY}px`, opacity:0}]);
        }
      } else if (Math.abs(dx) + Math.abs(dy) > 2 && effect.kind !== "reveal") {
        animate(node, [{translate:`${dx}px ${dy}px`}, {translate:"0px 0px"}]);
      }
    });
    content.append(layer);
    motion = {target, done, effect:true, comparisonOrigin, steps:[effect], index:0, elapsed:0, started:0, layer, animations};
    content.dataset.phase = "moving";
    content.dataset.transition = `${comparisonOrigin || from}->${target}`;
    if (comparisonOrigin) content.dataset.comparisonOrigin = comparisonOrigin;
    changeSummary?.setAttribute("aria-busy", "true");
    content.dataset.effect = effect.kind;
    if (transitionStatus) {
      transitionStatus.hidden = changeExplanations.size > 0;
      transitionStatus.textContent = {compare:"조건에 따른 결과 비교", transform:"입력과 결과의 변화", reveal:"세부 내용 펼치기·접기"}[effect.kind];
    }
    paint(0);
    updatePlayback();
    resumeMotion();
  }
  function travel(target, done, comparisonOrigin = null) {
    const from = comparisonOrigin || content.dataset.state;
    const edge = transitions.get(`${from}->${target}`);
    const effect = stateEffects.get(`${from}->${target}`);
    if (effect && !reduced.matches) {
      changeValues(target, effect, done, comparisonOrigin);
      return;
    }
    if (!edge || !edge.steps.length || reduced.matches) {
      show(target, true, true, comparisonOrigin);
      done();
      return;
    }
    cancelEffects();
    const layer = document.createElement("div");
    layer.className = "scene-transfer-layer";
    layer.setAttribute("aria-hidden", "true");
    Object.assign(layer.style, {position: "absolute", inset: "0", pointerEvents: "none", zIndex: "10"});
    const wire = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    wire.classList.add("scene-transfer-wire");
    Object.assign(wire.style, {position: "absolute", width: "100%", height: "100%", inset: "0", overflow: "visible"});
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "2");
    path.setAttribute("stroke-dasharray", "5 5");
    wire.append(path);
    const token = document.createElement("span");
    token.className = "scene-transfer-token";
    Object.assign(token.style, {position: "absolute", translate: "-50% -50%", pointerEvents: "none"});
    layer.append(wire, token);
    content.append(layer);
    motion = {target, done, steps: edge.steps, index: 0, elapsed: 0, started: 0, layer, wire, path, token};
    content.dataset.phase = "moving";
    content.dataset.transition = `${from}->${target}`;
    prepareStep();
    updatePlayback();
    resumeMotion();
  }

  function schedule() {
    if (motion) { resumeMotion(); return; }
    if (intent !== "playing" || timer !== null || !visible || document.hidden) return;
    due = performance.now() + remaining;
    timer = setTimeout(() => {
      timer = null;
      if (!visible || document.hidden) { remaining = 0; updatePlayback(); return; }
      remaining = playback.interval_ms;
      travel(route[position + 1], () => {
        if (position >= route.length - 1) {
          intent = "complete";
          updatePlayback();
        } else schedule();
      });
    }, remaining);
    updatePlayback();
  }
  function start() {
    if (motion) {
      intent = resumeIntent;
      resumeMotion();
      return;
    }
    if (route.length < 2) return;
    if (position < 0 || position === route.length - 1) {
      history = [];
      show(scene.initial);
      remaining = playback.interval_ms;
    }
    intent = "playing";
    resumeIntent = "playing";
    updatePlayback(); // Reflect intent even while visibility delays scheduling.
    schedule();
  }
  function reset() {
    automaticUsed = true;
    cancelPending();
    intent = "idle";
    history = [];
    route = playback.steps;
    selectedScenario = (scene.scenarios || []).find(option => JSON.stringify(option.steps) === JSON.stringify(route))?.id || "";
    show(scene.initial);
    focusExplanation();
  }
  document.getElementById("scene-reset").addEventListener("click", reset);
  if (next) next.addEventListener("click", () => {
    if (motion || position < 0 || position >= route.length - 1) return;
    const target = route[position + 1];
    const index = states.get(content.dataset.state).actions.findIndex(action => action.target === target);
    document.querySelector(`button[data-action="${index}"]`)?.click();
  });
  if (previous) previous.addEventListener("click", () => {
    automaticUsed = true;
    const wasMoving = Boolean(motion);
    cancelPending();
    intent = "paused";
    // During a transfer, go back to its unchanged source. A second click
    // then goes to the preceding settled state in the reader's own history.
    if (!wasMoving && history.length > 1) history.pop();
    show(history[history.length - 1] || scene.initial, false, false);
    focusExplanation();
  });
  if (scenarioControls) {
    scenarioControls.hidden = !(scene.scenarios || []).length;
    (scene.scenarios || []).forEach(option => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = directScenarios.has(option.id) ? initialActions.find(action => action.target === option.steps[1]).label : option.label;
      button.dataset.scenario = option.id;
      if (directScenarios.has(option.id)) button.dataset.scenarioAction = "true";
      button.addEventListener("click", () => {
        if (motion && directScenarios.has(option.id)) return;
        // Alternate results are views of the same input, not a new domain
        // transition between outcomes. Keep the old view while changing values;
        // history, explanation and replay still start at the declared origin.
        const target = option.steps[1];
        if (manualDefault && directScenarios.has(option.id) &&
            changeExplanations.has(`${scene.initial}->${target}`) &&
            stateEffects.has(`${scene.initial}->${target}`) && content.dataset.state !== scene.initial) {
          if (content.dataset.state === target) { focusExplanation(); return; }
          selectedScenario = option.id;
          route = option.steps;
          act(target, scene.initial);
          return;
        }
        reset(); // A long route choice is not permission to restart autoplay.
        selectedScenario = option.id;
        route = option.steps;
        if (directScenarios.has(option.id)) act(option.steps[1]);
        else selectedScenario = option.id;
        updatePlayback();
        document.getElementById("scene-playback").hidden = route.length < 2;
      });
      scenarioControls.append(button);
    });
  }
  play.addEventListener("click", () => {
    automaticUsed = true;
    if (running()) pause();
    else {
      revealStage();
      start();
    }
  });
  document.getElementById("scene-playback").hidden = route.length < 2;
  document.getElementById("scene-interaction").hidden = scene.states.length === 1;
  show(scene.initial);
  function reconcileVisibility() {
    if (!visible || document.hidden) { suspend(); return; }
    if (running()) effects.forEach(effect => { if (effect.playState === "paused") effect.play(); });
    if (running()) schedule();
    else if (!automaticUsed && !manualDefault && !reduced.matches && route.length > 1) {
      automaticUsed = true;
      start();
    }
  }
  const observer = new IntersectionObserver(entries => {
    visible = entries[0].isIntersecting && entries[0].intersectionRatio >= 0.5;
    reconcileVisibility();
  }, {threshold: [0, 0.5]});
  observer.observe(content);
  document.addEventListener("visibilitychange", reconcileVisibility);
  reduced.addEventListener("change", () => {
    if (reduced.matches) {
      automaticUsed = true;
      pause();
      if (motion) completeMotion(); // Preserve the result, without movement.
      intent = "paused";
      updatePlayback();
    }
  });
  new ResizeObserver(resize).observe(document.body);
  window.addEventListener("resize", () => {
    if (diagram) diagram.draw(content, scene);
    if (motion) {
      const elapsed = motion.elapsed + (frame === null ? 0 : Math.max(0, performance.now() - motion.started));
      paint(elapsed / motion.steps[motion.index].duration_ms);
    }
    resize();
  });
})();
