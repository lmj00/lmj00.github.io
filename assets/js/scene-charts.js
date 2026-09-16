/* Trusted numeric drawings. Model data never becomes markup, code or a URL. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var tones = {blue: '#79b8ff', amber: '#ffb86b', teal: '#69cdb4'};
  var css = '.scene-chart{box-sizing:border-box;min-width:0;max-width:100%;margin:12px 0 16px;color:#d6dae0;font:inherit;overflow-wrap:anywhere}' +
    '.scene-chart *{box-sizing:border-box}.scene-chart-title{margin:0 0 8px;font-size:14px;font-weight:700;line-height:1.5}' +
    '.scene-chart-legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 8px;font-size:13px;line-height:1.5}' +
    '.scene-chart-key{display:inline-flex;gap:6px;align-items:center;min-width:0}.scene-chart-swatch{flex:0 0 20px;border-top:3px solid}' +
    '.scene-chart-plot{display:grid;grid-template-columns:52px minmax(0,1fr);gap:6px;align-items:start}' +
    '.scene-chart-y{position:relative;height:154px;font-size:12px;color:#8b93a1;line-height:1.2;font-variant-numeric:tabular-nums}' +
    '.scene-chart-tick{position:absolute;right:0;max-width:100%;transform:translateY(-50%);overflow-wrap:anywhere}' +
    '.scene-chart-graphic{display:block;width:100%;height:154px;overflow:visible}.scene-chart-axis{display:grid;gap:2px;margin:5px 0 0 58px;font-size:12px;line-height:1.4;color:#8b93a1}' +
    '.scene-chart-axis span{min-width:0;text-align:center;overflow-wrap:anywhere}' +
    '.scene-chart-caption{margin:8px 0 0;font-size:13px;line-height:1.5;color:#8b93a1}' +
    '.scene-chart-details{margin:6px 0 0;font-size:13px;line-height:1.5}.scene-chart-details summary{cursor:pointer;text-decoration:underline;text-underline-offset:3px}' +
    '.scene-chart-details summary:focus-visible{outline:2px solid #79b8ff;outline-offset:3px}.scene-chart-table-wrap{max-width:100%;overflow:auto}' +
    '.scene-chart-table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;table-layout:fixed;margin:8px 0 0}' +
    '.scene-chart-table th,.scene-chart-table td{padding:5px 4px;text-align:right;border-bottom:1px solid #364354;overflow-wrap:anywhere}' +
    '.scene-chart-table th:first-child,.scene-chart-table td:first-child{text-align:left}.scene-chart-table caption{text-align:left;font-size:13px}';

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svg(tag, attrs) {
    var node = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, String(attrs[key]));
      // CSS normally outranks SVG presentation attributes. These trusted numbers
      // and paints must not be changed by a model's generic attribute selector.
      if (['x', 'y', 'cx', 'cy', 'r', 'width', 'height', 'fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'fill-opacity', 'vector-effect'].indexOf(key) >= 0) {
        var geometry = ['x', 'y', 'cx', 'cy', 'r', 'width', 'height'].indexOf(key) >= 0;
        node.style.setProperty(key, String(attrs[key]) + (geometry ? 'px' : ''));
      }
    });
    node.style.opacity = '1'; node.style.visibility = 'visible';
    node.style.strokeOpacity = '1';
    if (!attrs || attrs['fill-opacity'] === undefined) node.style.fillOpacity = '1';
    node.style.transform = 'none'; node.style.filter = 'none';
    node.style.clipPath = 'none'; node.style.mask = 'none';
    if (tag === 'svg') { node.style.width = '100%'; node.style.height = '154px'; node.style.display = 'block'; }
    else node.style.display = 'inline';
    return node;
  }
  function installStyle() {
    if (document.getElementById('scene-chart-style')) return;
    var style = el('style');
    style.id = 'scene-chart-style'; style.textContent = css;
    document.head.appendChild(style);
  }
  function number(value) { return Object.is(value, -0) ? '0' : String(value); }
  function tick(value) {
    if (Math.abs(value) >= 10000 || (value !== 0 && Math.abs(value) < 0.001)) return value.toExponential(1).replace('.0e', 'e').replace('e+', 'e');
    return value.toLocaleString('en-US', {maximumSignificantDigits: 4});
  }
  function valid(chart, stateId) {
    // Defense in depth for a malformed saved page; the Python contract is stricter.
    if (!chart || !/^[a-z][a-z0-9_-]{0,31}$/.test(chart.entity) ||
        ['line', 'bar'].indexOf(chart.kind) < 0 || !Array.isArray(chart.labels) ||
        chart.labels.length < 2 || chart.labels.length > 12 || !Array.isArray(chart.series) ||
        !chart.series.length || chart.series.length > 3 || !Array.isArray(chart.views)) return null;
    var ids = new Set();
    if (!chart.series.every(function (series) {
      if (!series || typeof series.id !== 'string' || ids.has(series.id) || !tones[series.tone] ||
          !Array.isArray(series.values) || series.values.length !== chart.labels.length ||
          !series.values.every(function (value) { return Number.isFinite(value) && Math.abs(value) <= 1e12; })) return false;
      ids.add(series.id); return true;
    })) return null;
    var views = chart.views.filter(function (view) { return view && view.state === stateId; });
    if (views.length !== 1) return null;
    var view = views[0];
    if (!Number.isInteger(view.visible_points) || view.visible_points < 1 || view.visible_points > chart.labels.length ||
        !Array.isArray(view.active_series) || !view.active_series.length ||
        new Set(view.active_series).size !== view.active_series.length ||
        !view.active_series.every(function (id) { return ids.has(id); })) return null;
    return view;
  }
  function make(chart, view, open) {
    var root = el('figure', 'scene-chart');
    root.setAttribute('data-chart-for', chart.entity);
    root.setAttribute('data-chart-state', view.state);
    var active = chart.series;
    function selected(series) { return view.active_series.indexOf(series.id) >= 0; }
    var values = chart.series.reduce(function (all, series) { return all.concat(series.values); }, [0]);
    var low = Math.min.apply(null, values), high = Math.max.apply(null, values);
    if (low === high) high = low + 1;
    root.setAttribute('data-chart-min', number(low));
    root.setAttribute('data-chart-max', number(high));
    root.setAttribute('data-chart-visible-points', String(view.visible_points));
    var title = el('figcaption', 'scene-chart-title', chart.label + (chart.unit ? ' · ' + chart.unit : ''));
    root.appendChild(title);
    var legend = el('div', 'scene-chart-legend');
    active.forEach(function (series) {
      var key = el('span', 'scene-chart-key'), swatch = el('span', 'scene-chart-swatch');
      swatch.style.borderColor = tones[series.tone];
      if (chart.series.indexOf(series) === 1) swatch.style.borderTopStyle = 'dashed';
      if (chart.series.indexOf(series) === 2) swatch.style.borderTopStyle = 'dotted';
      swatch.setAttribute('aria-hidden', 'true'); key.appendChild(swatch);
      key.setAttribute('data-chart-active', String(selected(series)));
      key.style.fontWeight = selected(series) ? '700' : '400';
      key.appendChild(document.createTextNode(series.label + (selected(series) ? ' · 선택' : ''))); legend.appendChild(key);
    });
    root.appendChild(legend);
    var plot = el('div', 'scene-chart-plot'), axis = el('div', 'scene-chart-y');
    var drawing = svg('svg', {viewBox: '0 0 600 154', preserveAspectRatio: 'none', role: 'img', class: 'scene-chart-graphic'});
    drawing.setAttribute('aria-label', chart.label + '. ' + active.map(function (series) { return series.label; }).join(', ') + '. 정확한 값은 수치 표에서 확인하세요.');
    function y(value) { return 8 + (high - value) / (high - low) * 138; }
    function x(index) { return (index + 0.5) / chart.labels.length * 600; }
    var ticks = [high, low];
    if (low < 0 && high > 0) ticks.push(0);
    ticks.forEach(function (value) {
      var mark = el('span', 'scene-chart-tick', tick(value));
      mark.style.top = y(value) + 'px'; mark.title = number(value); axis.appendChild(mark);
      drawing.appendChild(svg('line', {x1: 0, y1: y(value), x2: 600, y2: y(value), stroke: value === 0 ? '#66758b' : '#364354', 'stroke-width': 1, 'vector-effect': 'non-scaling-stroke'}));
    });
    active.forEach(function (series, seriesIndex) {
      var points = series.values.slice(0, view.visible_points);
      if (chart.kind === 'line') {
        var line = svg('polyline', {points: points.map(function (value, index) { return x(index) + ',' + y(value); }).join(' '), fill: 'none', stroke: tones[series.tone], 'stroke-width': selected(series) ? 3 : 1.5, 'vector-effect': 'non-scaling-stroke', 'data-chart-series': series.id, 'data-chart-active': selected(series)});
        if (chart.series.indexOf(series) === 1) line.style.strokeDasharray = '7 4';
        if (chart.series.indexOf(series) === 2) line.style.strokeDasharray = '2 4';
        drawing.appendChild(line);
      }
      points.forEach(function (value, index) {
        var attrs = {'data-chart-series': series.id, 'data-chart-index': index, 'data-chart-value': number(value), 'data-chart-active': selected(series), fill: tones[series.tone]};
        var mark;
        if (chart.kind === 'bar') {
          var group = 600 / chart.labels.length, width = Math.min(62, group * 0.76 / active.length);
          attrs.x = (index + 0.5) * group - width * active.length / 2 + width * seriesIndex;
          attrs.y = Math.min(y(0), y(value)); attrs.width = Math.max(1, width - 2); attrs.height = Math.abs(y(value) - y(0));
          attrs['fill-opacity'] = selected(series) ? 1 : 0.65;
          mark = svg('rect', attrs);
        } else {
          attrs.cx = x(index); attrs.cy = y(value); attrs.r = selected(series) ? 4.5 : 2.5;
          mark = svg('circle', attrs);
        }
        var tooltip = svg('title'); tooltip.textContent = series.label + ' · ' + chart.labels[index] + ': ' + number(value) + (chart.unit ? ' ' + chart.unit : '');
        mark.appendChild(tooltip); drawing.appendChild(mark);
      });
    });
    plot.appendChild(axis); plot.appendChild(drawing); root.appendChild(plot);
    var labels = el('div', 'scene-chart-axis');
    var numbered = chart.labels.length > 4 || chart.labels.some(function (label) { return String(label).length > 12; });
    labels.style.gridTemplateColumns = 'repeat(' + chart.labels.length + ', minmax(0, 1fr))';
    chart.labels.forEach(function (label, index) { labels.appendChild(el('span', '', numbered ? String(index + 1) : label)); });
    root.appendChild(labels);
    root.appendChild(el('p', 'scene-chart-caption', chart.caption));
    var details = el('details', 'scene-chart-details'); details.open = open;
    details.appendChild(el('summary', '', numbered ? '관측 지점 번호와 정확한 수치 표 보기' : '정확한 수치 표 보기'));
    var wrap = el('div', 'scene-chart-table-wrap'), table = el('table', 'scene-chart-table');
    table.appendChild(el('caption', '', chart.label + (chart.unit ? ' (' + chart.unit + ')' : '')));
    var head = el('thead'), heading = el('tr'), first = el('th', '', '관측 지점'); first.scope = 'col'; heading.appendChild(first);
    active.forEach(function (series) { var cell = el('th', '', series.label); cell.scope = 'col'; heading.appendChild(cell); });
    head.appendChild(heading); table.appendChild(head);
    var body = el('tbody');
    chart.labels.slice(0, view.visible_points).forEach(function (label, index) {
      var row = el('tr'), name = el('th', '', (numbered ? String(index + 1) + ' · ' : '') + label); name.scope = 'row'; row.appendChild(name);
      active.forEach(function (series) {
        var cell = el('td', '', number(series.values[index]));
        cell.setAttribute('data-chart-series', series.id); cell.setAttribute('data-chart-index', String(index));
        row.appendChild(cell);
      }); body.appendChild(row);
    });
    table.appendChild(body); wrap.appendChild(table); details.appendChild(wrap); root.appendChild(details);
    return root;
  }
  function draw(content, scene, stateId) {
    if (!content || !scene) return;
    var existing = Array.from(content.querySelectorAll('[data-chart-for]'));
    var opened = new Set(existing.filter(function (node) { return node.querySelector('details[open]'); }).map(function (node) { return node.getAttribute('data-chart-for'); }));
    existing.forEach(function (node) { node.remove(); });
    if (!Array.isArray(scene.charts) || !scene.charts.length || scene.charts.length > 2) return;
    installStyle();
    var seen = new Set();
    scene.charts.forEach(function (chart) {
      var view = valid(chart, stateId);
      if (!view || seen.has(chart.entity)) return;
      seen.add(chart.entity);
      var hosts = Array.from(content.querySelectorAll('[data-entity]')).filter(function (node) { return node.getAttribute('data-entity') === chart.entity; });
      if (hosts.length !== 1) return;
      var host = hosts[0];
      if (['DIV', 'SECTION', 'ARTICLE'].indexOf(host.tagName) < 0 || !host.textContent.trim() || host.querySelector('[data-entity]') || host.parentElement.closest('[data-entity]')) return;
      host.insertAdjacentElement('afterend', make(chart, view, opened.has(chart.entity)));
    });
  }
  window.ArticleCharts = Object.freeze({draw: draw});
}());
