/* Trusted glyphs and topology for the finite-state player; never model-authored JS. */
window.ArticleDiagram = (() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const glyphs = {
    producer: '<rect x="4" y="7" width="13" height="15" rx="2"/><path d="M8 11h5M8 15h5M19 3v10m-4-6 4-4 4 4"/>',
    consumer: '<rect x="3" y="4" width="22" height="15" rx="3"/><path d="M9 24h10M14 19v5m-4-15-3 3 3 3m8-6 3 3-3 3"/>',
    queue: '<rect x="3" y="5" width="5" height="19" rx="1"/><rect x="12" y="5" width="5" height="19" rx="1"/><rect x="21" y="5" width="5" height="19" rx="1"/>',
    exchange: '<path d="m14 3 11 11-11 11L3 14Z"/><path d="M8 14h11m-4-4 4 4-4 4"/>',
    server: '<rect x="3" y="3" width="22" height="9" rx="2"/><rect x="3" y="16" width="22" height="9" rx="2"/><path d="M7 7h1m4 0h9M7 20h1m4 0h9"/>',
    database: '<ellipse cx="14" cy="6" rx="10" ry="4"/><path d="M4 6v16c0 5 20 5 20 0V6M4 14c0 5 20 5 20 0"/>',
    cache: '<path d="M6 7a10 10 0 1 1-2 12M6 2v6H1m15-4-6 11h7l-5 9"/>',
    document: '<path d="M6 2h10l7 7v17H6Zm10 0v7h7M10 14h9m-9 5h9"/>'
  };
  function svg(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key,value]) => node.setAttribute(key, value));
    return node;
  }
  function anchor(node) { return node?.querySelector(".diagram-symbol") || node; }
  function geometry(content, source, target) {
    const origin = content.getBoundingClientRect();
    const a = anchor(source).getBoundingClientRect(), b = anchor(target).getBoundingClientRect();
    const start = {x:a.x+a.width/2-origin.x, y:a.y+a.height/2-origin.y};
    const end = {x:b.x+b.width/2-origin.x, y:b.y+b.height/2-origin.y};
    const horizontal = Math.abs(end.x-start.x) > Math.abs(end.y-start.y);
    const c1 = horizontal ? {x:(start.x+end.x)/2,y:start.y} : {x:start.x,y:(start.y+end.y)/2};
    const c2 = horizontal ? {x:(start.x+end.x)/2,y:end.y} : {x:end.x,y:(start.y+end.y)/2};
    return {start,end,c1,c2,width:origin.width,height:origin.height};
  }
  function point(g,t) {
    const u=1-t;
    return {x:u**3*g.start.x+3*u*u*t*g.c1.x+3*u*t*t*g.c2.x+t**3*g.end.x,
      y:u**3*g.start.y+3*u*u*t*g.c1.y+3*u*t*t*g.c2.y+t**3*g.end.y};
  }
  function path(g) {return `M${g.start.x},${g.start.y} C${g.c1.x},${g.c1.y} ${g.c2.x},${g.c2.y} ${g.end.x},${g.end.y}`;}
  function icons(content) {
    content.querySelectorAll("span[data-icon]").forEach(symbol => {
      if (symbol.querySelector("svg") || !Object.hasOwn(glyphs, symbol.dataset.icon)) return;
      const icon = svg("svg", {viewBox:"0 0 28 28", "aria-hidden":"true"});
      icon.innerHTML = glyphs[symbol.dataset.icon]; // Trusted constants only.
      symbol.replaceChildren(icon);
    });
  }
  function draw(content, scene) {
    icons(content);
    const board = content.querySelector(".diagram-board");
    if (!board) return;
    const nodes = new Map([...board.querySelectorAll(".diagram-node")].map(n => [n.dataset.entity,n]));
    board.style.setProperty("--node-count", nodes.size);
    // Recalculate from stylesheet defaults, never accumulate space on resize.
    board.style.removeProperty("row-gap");
    board.style.removeProperty("padding-top");
    board.querySelectorAll(".diagram-symbol[data-icon]").forEach(symbol => {
      if (symbol.querySelector("svg")) return;
      const icon = svg("svg", {viewBox:"0 0 28 28", "aria-hidden":"true"});
      icon.innerHTML = glyphs[symbol.dataset.icon] || glyphs.document; // Constant allowlist, never input HTML.
      symbol.replaceChildren(icon);
    });
    content.querySelector(".diagram-links")?.remove();
    content.querySelector(".diagram-labels")?.remove();
    const labels = document.createElement("div");
    labels.className = "diagram-labels";
    content.prepend(labels);
    const mobile = innerWidth <= 560;
    const branch = scene.presentation.layout === "branch";
    const items = scene.presentation.links.map(link => {
      const source = nodes.get(link.source), target = nodes.get(link.target);
      if (!source || !target) return null;
      const g = geometry(content, source, target);
      const vertical = g.end.y > g.start.y + 40;
      const label = document.createElement("span");
      label.className = "diagram-link-label";
      label.textContent = link.label; // Plain data, never markup or SVG source.
      const corridor = Math.abs(g.end.x - g.start.x) -
        (anchor(source).getBoundingClientRect().width + anchor(target).getBoundingClientRect().width) / 2 - 16;
      label.style.maxWidth = `${Math.min(content.clientWidth - 16,
        vertical ? (mobile && branch ? content.clientWidth / 2 - 24 : 144) : Math.max(64, corridor))}px`;
      labels.append(label);
      const wrapped = label.getBoundingClientRect().height > 17;
      // The single horizontal mobile branch label gets its own top lane when
      // long. Vertical labels use real inter-row space, not the node's caption.
      const topLane = mobile && branch && !vertical && wrapped;
      if (topLane) label.style.maxWidth = `${content.clientWidth - 16}px`;
      return {link, source, target, label, vertical, wrapped, topLane};
    }).filter(Boolean);
    if (mobile) {
      const rowHeight = Math.max(0, ...items.filter(item => item.vertical && item.wrapped)
        .map(item => item.label.getBoundingClientRect().height + 16));
      if (rowHeight) board.style.rowGap = `${Math.max(parseFloat(getComputedStyle(board).rowGap) || 0, rowHeight)}px`;
      const topHeight = Math.max(0, ...items.filter(item => item.topLane)
        .map(item => item.label.getBoundingClientRect().height + 16));
      if (topHeight) board.style.paddingTop = `${parseFloat(getComputedStyle(board).paddingTop) + topHeight}px`;
    }
    const layer = svg("svg", {class:"diagram-links", "aria-hidden":"true"});
    layer.setAttribute("viewBox", `0 0 ${content.clientWidth} ${content.clientHeight}`);
    items.forEach(({source,target,label,vertical,wrapped,topLane}) => {
      const g=geometry(content,source,target), mid=point(g,.5);
      layer.append(svg("path", {d:path(g),class:`diagram-link${source.classList.contains("is-active") && target.classList.contains("is-active") ? " is-active" : ""}`}));
      const mobileBranch = mobile && branch && vertical;
      const bounds = label.getBoundingClientRect();
      const x = mobileBranch ? g.end.x : mid.x;
      let y = (mobileBranch ? mid.y + 20 : mid.y - 12) - 12 - (bounds.height - 16) / 2;
      if (topLane) y = 4;
      else if (mobile && vertical && wrapped) {
        const origin = content.getBoundingClientRect();
        y = (source.getBoundingClientRect().bottom + target.getBoundingClientRect().top) / 2 - origin.y - bounds.height / 2;
      }
      label.style.left = `${Math.max(4, Math.min(content.clientWidth - bounds.width - 4, x - bounds.width / 2))}px`;
      label.style.top = `${Math.max(4, Math.min(content.clientHeight - bounds.height - 4, y))}px`;
    });
    content.prepend(layer);
  }
  return {draw,icons,geometry,point,path};
})();
