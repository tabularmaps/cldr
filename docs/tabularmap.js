/*
 * tabularmap.js — rendering core of the CLDR tabular map (no dependencies, SVG).
 *
 *   const map = TabularMap.create(container, { layout, regions });
 *   map.setSeries({ label: 'Population', unit: 'M', values: { JP: 124.5, ... } });
 *   map.setMode('value' | 'region');   // colour by data value / by CLDR subregion (default when no data)
 *   map.setScope('all' | 'un');        // 'un' mutes identifiers outside CLDR's UN grouping (cells stay in place)
 *   map.destroy();
 *
 * Data contract (see README.md): layout = layouts/<profile>-<W>x<H>.json (grid, placements,
 * structural_spaces); regions = data/regions.json (id, name_en, subregion, subregion_name,
 * continent_name, un_member). Series values are keyed by uppercase identifier; lowercase keys
 * are accepted. An identifier without a value is drawn in the "no data" colour.
 *
 * Drawing rules: values use a single-hue sequential ramp; subregion colours identify regions only
 * when there is no data; labels are always ink-coloured (white on dark cells); every cell has a
 * tooltip and the table view means nothing relies on colour alone.
 */
window.TabularMap = (function () {
  'use strict';

  const U = 40;      // cell unit
  const GAP = 2;     // gap between cells
  const SEQ = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5',
               '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b'];
  // CLDR/M49 subregion -> colour family (same palette as cldrmap/render.py)
  const REGION = {
    '021': '#6c8ebf', '013': '#7f9ccf', '029': '#93a9d9', '005': '#5f7fb5',
    '154': '#c76b6b', '155': '#d17f7f', '151': '#b85c5c', '039': '#d99191',
    '015': '#d9a441', '011': '#e0b35a', '017': '#c99a3a', '014': '#e6c27a', '018': '#bf8f2e',
    '145': '#7fb37f', '143': '#6aa36a', '034': '#8fc08f', '035': '#a3cda3', '030': '#5e955e',
    '053': '#a67fc7', '054': '#b592d1', '057': '#c4a6db', '061': '#d2bae5'
  };
  const CONTINENT_SWATCH = [
    ['Americas', '#6c8ebf'], ['Europe', '#c76b6b'], ['Africa', '#d9a441'], ['Asia', '#7fb37f'], ['Oceania', '#a67fc7']
  ];

  function hexToRgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
  function rgbToHex(r) { return '#' + r.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join(''); }
  function luminance(hex) {
    const [r, g, b] = hexToRgb(hex).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function ramp(t) {
    t = Math.max(0, Math.min(1, t));
    const p = t * (SEQ.length - 1), i = Math.floor(p), f = p - i;
    if (i >= SEQ.length - 1) return SEQ[SEQ.length - 1];
    const a = hexToRgb(SEQ[i]), b = hexToRgb(SEQ[i + 1]);
    return rgbToHex(a.map((v, k) => v + (b[k] - v) * f));
  }
  function inkFor(fill) { return luminance(fill) < 0.3 ? '#ffffff' : '#0b0b0b'; }
  function fmt(v, unit) {
    if (v == null || Number.isNaN(v)) return '—';
    const s = Math.abs(v) >= 100 ? Math.round(v).toLocaleString('en-US') : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);
    return unit ? `${s} ${unit}` : s;
  }
  function el(tag, attrs, parent) {
    const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function create(container, opts) {
    const layout = opts.layout;
    const regions = (opts.regions && opts.regions.regions) || [];
    const byId = new Map(regions.map((r) => [r.id, r]));
    const W = layout.grid[0], H = layout.grid[1];
    const state = { mode: opts.mode || 'region', series: null, scope: opts.scope || 'all', showTable: false };

    const root = document.createElement('div');
    root.className = 'tm-root';
    container.appendChild(root);

    const head = document.createElement('div'); head.className = 'tm-head'; root.appendChild(head);
    const titleEl = document.createElement('div'); titleEl.className = 'tm-title'; head.appendChild(titleEl);
    const legend = document.createElement('div'); legend.className = 'tm-legend'; head.appendChild(legend);
    const controls = document.createElement('div'); controls.className = 'tm-controls'; head.appendChild(controls);
    const btnMode = document.createElement('button'); btnMode.type = 'button'; btnMode.className = 'tm-btn'; controls.appendChild(btnMode);
    const btnScope = document.createElement('button'); btnScope.type = 'button'; btnScope.className = 'tm-btn'; controls.appendChild(btnScope);
    const btnTable = document.createElement('button'); btnTable.type = 'button'; btnTable.className = 'tm-btn'; controls.appendChild(btnTable);

    const stage = document.createElement('div'); stage.className = 'tm-stage'; root.appendChild(stage);
    const svg = el('svg', { viewBox: `0 0 ${W * U} ${H * U}`, class: 'tm-svg', role: 'img' }, stage);
    svg.style.aspectRatio = `${W} / ${H}`;
    el('title', {}, svg).textContent = 'CLDR tabular map';
    const tip = document.createElement('div'); tip.className = 'tm-tip'; tip.hidden = true; stage.appendChild(tip);
    const tableWrap = document.createElement('div'); tableWrap.className = 'tm-table'; tableWrap.hidden = true; root.appendChild(tableWrap);

    for (const s of layout.structural_spaces) {
      el('rect', { x: s[0] * U + GAP / 2, y: s[1] * U + GAP / 2, width: U - GAP, height: U - GAP, rx: 3, class: 'tm-space' }, svg);
    }
    const cells = [];
    for (const p of layout.placements) {
      const r = byId.get(p.id) || {};
      const g = el('g', { class: 'tm-cell', 'data-id': p.id }, svg);
      const x = p.x * U + GAP / 2, y = p.y * U + GAP / 2, w = p.w * U - GAP, h = p.h * U - GAP;
      const rect = el('rect', { x, y, width: w, height: h, rx: 3 }, g);
      const text = el('text', { x: x + w / 2, y: y + h / 2, 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 14 }, g);
      text.textContent = p.id;
      const c = { id: p.id, name: r.name_en || p.id, subregion: r.subregion, subregionName: r.subregion_name || '',
                  continent: r.continent_name || '', un: !!r.un_member, g, rect, text };
      cells.push(c);
      g.addEventListener('mousemove', (ev) => showTip(c, ev));
      g.addEventListener('mouseleave', hideTip);
      g.addEventListener('click', () => { if (opts.onSelect) opts.onSelect(c.id, c); });
    }

    function inScope(c) { return state.scope !== 'un' || c.un; }
    function valueOf(id) {
      const s = state.series;
      if (!s || !s.values) return undefined;
      let v = s.values[id];
      if (v === undefined) v = s.values[id.toLowerCase()];
      return typeof v === 'number' && !Number.isNaN(v) ? v : undefined;
    }
    function range() {
      const s = state.series;
      if (!s) return [0, 1];
      const vals = cells.filter(inScope).map((c) => valueOf(c.id)).filter((v) => v !== undefined);
      const lo = s.min != null ? s.min : (vals.length ? Math.min(...vals) : 0);
      const hi = s.max != null ? s.max : (vals.length ? Math.max(...vals) : 1);
      return [lo, hi > lo ? hi : lo + 1];
    }

    function paint() {
      const [lo, hi] = range();
      const valueMode = state.mode === 'value' && state.series;
      for (const c of cells) {
        if (!inScope(c)) {
          c.g.classList.add('tm-muted');
          c.rect.setAttribute('fill', 'none');
          c.text.setAttribute('fill', 'var(--tm-muted)');
          continue;
        }
        c.g.classList.remove('tm-muted');
        let fill;
        if (valueMode) {
          const v = valueOf(c.id);
          fill = v === undefined ? 'var(--tm-nodata)' : ramp((v - lo) / (hi - lo));
        } else {
          fill = REGION[c.subregion] || 'var(--tm-nodata)';
        }
        c.rect.setAttribute('fill', fill);
        c.text.setAttribute('fill', fill.startsWith('#') ? inkFor(fill) : 'var(--tm-ink)');
      }
      legend.innerHTML = '';
      if (valueMode) {
        const bar = document.createElement('div'); bar.className = 'tm-legend-bar';
        bar.style.background = `linear-gradient(90deg, ${SEQ.join(',')})`;
        const lo_ = document.createElement('span'); lo_.textContent = fmt(lo, state.series.unit);
        const hi_ = document.createElement('span'); hi_.textContent = fmt(hi, state.series.unit);
        legend.append(lo_, bar, hi_);
        const nd = document.createElement('span'); nd.className = 'tm-legend-nodata'; nd.textContent = 'no data';
        legend.appendChild(nd);
      } else {
        for (const [name, color] of CONTINENT_SWATCH) {
          const sw = document.createElement('span'); sw.className = 'tm-legend-sw';
          sw.innerHTML = `<i style="background:${color}"></i>${name}`;
          legend.appendChild(sw);
        }
      }
      if (state.scope === 'un') {
        const sc = document.createElement('span'); sc.className = 'tm-legend-scope';
        sc.textContent = 'outlined: outside CLDR’s UN grouping';
        legend.appendChild(sc);
      }
      titleEl.textContent = valueMode
        ? `${state.series.label || ''}${state.series.asOf ? ' ' + state.series.asOf : ''}`
        : (opts.title || 'CLDR tabular map');
      btnMode.textContent = state.mode === 'value' ? 'Colour by subregion' : 'Colour by value';
      btnMode.disabled = !state.series;
      btnScope.textContent = state.scope === 'un' ? 'Show all identifiers' : 'UN members only';
      btnScope.title = 'Mutes identifiers outside the UN grouping of CLDR territoryContainment (193 members); every cell keeps its place.';
      btnTable.textContent = state.showTable ? 'Hide table' : 'Show table';
      tableWrap.hidden = !state.showTable;
      if (state.showTable) renderTable();
    }

    function renderTable() {
      const s = state.series;
      const rows = cells.filter(inScope).map((c) => ({ id: c.id, name: c.name, sub: c.subregionName, v: valueOf(c.id) }));
      if (s) rows.sort((a, b) => (b.v ?? -Infinity) - (a.v ?? -Infinity));
      const t = document.createElement('table');
      t.innerHTML = `<thead><tr><th>id</th><th>name (CLDR en)</th><th>subregion</th><th>${s ? esc(s.label || 'value') + (s.unit ? ` (${esc(s.unit)})` : '') : ''}</th></tr></thead>`;
      const tb = document.createElement('tbody');
      for (const r of rows) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${r.id}</td><td>${esc(r.name)}</td><td>${esc(r.sub)}</td><td class="tm-num">${s ? fmt(r.v) : ''}</td>`;
        tb.appendChild(tr);
      }
      t.appendChild(tb);
      tableWrap.innerHTML = '';
      tableWrap.appendChild(t);
    }

    function showTip(c, ev) {
      const v = valueOf(c.id);
      const s = state.series;
      tip.innerHTML = `<b>${c.id} ${esc(c.name)}</b><span class="tm-tip-sub">${esc(c.subregionName)} · ${esc(c.continent)}</span>`
        + (state.scope === 'un' && !c.un ? '<span class="tm-tip-sub">outside CLDR’s UN grouping</span>' : '')
        + (s && inScope(c) ? `<span class="tm-tip-val">${esc(s.label || '')} ${fmt(v, s.unit)}</span>` : '');
      tip.hidden = false;
      const r = stage.getBoundingClientRect();
      let x = ev.clientX - r.left + 12, y = ev.clientY - r.top + 12;
      if (x + tip.offsetWidth > r.width) x = ev.clientX - r.left - tip.offsetWidth - 12;
      if (y + tip.offsetHeight > r.height) y = ev.clientY - r.top - tip.offsetHeight - 12;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
      for (const o of cells) o.g.classList.toggle('tm-hover', o === c);
    }
    function hideTip() { tip.hidden = true; for (const o of cells) o.g.classList.remove('tm-hover'); }

    btnMode.addEventListener('click', () => { state.mode = state.mode === 'value' ? 'region' : 'value'; paint(); });
    btnScope.addEventListener('click', () => { state.scope = state.scope === 'un' ? 'all' : 'un'; paint(); });
    btnTable.addEventListener('click', () => { state.showTable = !state.showTable; paint(); });

    paint();
    return {
      setSeries(series) { state.series = series || null; if (series) state.mode = 'value'; paint(); },
      setMode(mode) { state.mode = mode; paint(); },
      setScope(scope) { state.scope = scope; paint(); },
      highlight(id) { for (const o of cells) o.g.classList.toggle('tm-selected', o.id === id); },
      element: root,
      destroy() { if (root.parentNode) root.parentNode.removeChild(root); }
    };
  }

  return { create, ramp, REGION };
})();
