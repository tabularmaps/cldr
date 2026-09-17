/*
 * openmct-plugin.js — puts the CLDR tabular map into an Open MCT tree.
 *
 * Structure (following the Open MCT practice collected in dwg7/cafebabe and used by tabularmaps/do):
 *   - only objects.addProvider + composition.addProvider + objectViews.addProvider are used;
 *   - no Telemetry API and no Display Layout: each indicator ("source") exposes fetchValues() which
 *     the view calls directly and re-draws on a setInterval;
 *   - the root is a private type 'tabularmaps.cldr' (creatable: false) so built-in views do not compete.
 *
 * Usage:
 *   openmct.install(TabularMapsCldrPlugin({
 *     dataUrl: './data/',            // layout.json, regions.json
 *     sources: [
 *       { key: 'demo', name: 'Demo indicator', refreshMs: 5000,
 *         fetchValues: async () => ({ label: '…', unit: '…', asOf: '…', min: 0, max: 100, values: { JP: 12.3 } }) },
 *       { key: 'static', name: 'Static JSON', valuesUrl: './data/some-series.json' }
 *     ]
 *   }));
 *
 * Series shape: { label, unit, asOf, min, max, values: { <identifier>: number } }.
 * Identifiers without a value are drawn in the "no data" colour; subregion colours are only the
 * default when there is no data, so dashboard data owns the fill.
 */
window.TabularMapsCldrPlugin = function TabularMapsCldrPlugin(options) {
  'use strict';
  const NAMESPACE = (options && options.namespace) || 'tabularmaps-cldr';
  const dataUrl = (options && options.dataUrl) || './data/';
  const sources = (options && options.sources) || [];
  const ROOT_KEY = 'root';
  const MAP_KEY = 'map';

  let dataPromise = null;
  function loadData() {
    if (!dataPromise) {
      dataPromise = Promise.all([
        fetch(dataUrl + 'layout.json').then((r) => r.json()),
        fetch(dataUrl + 'regions.json').then((r) => r.json())
      ]).then(([layout, regions]) => ({ layout, regions }));
    }
    return dataPromise;
  }

  return function install(openmct) {
    openmct.types.addType('tabularmaps.cldr', {
      name: 'CLDR tabular map',
      description: 'Regular Unicode CLDR region identifiers, one equal cell each',
      creatable: false
    });

    const objects = new Map();
    objects.set(ROOT_KEY, { identifier: { namespace: NAMESPACE, key: ROOT_KEY }, name: 'CLDR tabular map',
                            type: 'tabularmaps.cldr', location: 'ROOT', tabularmap: { kind: 'root' } });
    objects.set(MAP_KEY, { identifier: { namespace: NAMESPACE, key: MAP_KEY }, name: 'World (subregion colours)',
                           type: 'tabularmaps.cldr', tabularmap: { kind: 'map' } });
    const children = [{ namespace: NAMESPACE, key: MAP_KEY }];
    for (const s of sources) {
      const key = 'source:' + s.key;
      objects.set(key, { identifier: { namespace: NAMESPACE, key }, name: s.name || s.key,
                         type: 'tabularmaps.cldr', tabularmap: { kind: 'source', source: s.key } });
      children.push({ namespace: NAMESPACE, key });
    }
    const sourceByKey = new Map(sources.map((s) => [s.key, s]));

    openmct.objects.addRoot({ namespace: NAMESPACE, key: ROOT_KEY });
    openmct.objects.addProvider(NAMESPACE, {
      get(identifier) {
        const o = objects.get(identifier.key);
        return o ? Promise.resolve(o) : Promise.reject(new Error('Unknown object ' + identifier.key));
      }
    });
    openmct.composition.addProvider({
      appliesTo(domainObject) {
        return domainObject.identifier.namespace === NAMESPACE && domainObject.identifier.key === ROOT_KEY;
      },
      load() { return Promise.resolve(children); }
    });

    async function fetchSeries(source) {
      if (typeof source.fetchValues === 'function') return source.fetchValues();
      if (source.valuesUrl) return fetch(source.valuesUrl, { cache: 'no-store' }).then((r) => r.json());
      return null;
    }

    openmct.objectViews.addProvider({
      key: 'tabularmaps.cldr.view',
      name: 'tabular map',
      canView(domainObject) {
        return domainObject.identifier.namespace === NAMESPACE && domainObject.type === 'tabularmaps.cldr';
      },
      view(domainObject) {
        let map = null, timer = null, host = null, disposed = false;
        return {
          show(element) {
            host = document.createElement('div');
            host.className = 'tm-openmct-host';
            host.style.height = '100%';
            element.appendChild(host);
            loadData().then((data) => {
              if (disposed) return;
              const kind = domainObject.tabularmap.kind;
              const source = kind === 'source' ? sourceByKey.get(domainObject.tabularmap.source) : null;
              map = window.TabularMap.create(host, {
                layout: data.layout, regions: data.regions, mode: 'region', title: domainObject.name,
                onSelect: (id, cell) => { if (source && source.onSelect) source.onSelect(id, cell); }
              });
              if (kind === 'root') {
                const note = document.createElement('div');
                note.className = 'tm-openmct-note';
                note.textContent = 'Pick an indicator in the tree to colour the cells by its values. Every identifier has one equal cell; blank cells are intentional whitespace.';
                host.appendChild(note);
              }
              if (source) {
                const tick = () => fetchSeries(source).then((s) => { if (!disposed && s) map.setSeries(s); })
                  .catch(() => { /* keep the previous drawing when an indicator fails */ });
                tick();
                if (source.refreshMs) timer = setInterval(tick, source.refreshMs);
              }
            });
          },
          destroy() {
            disposed = true;
            if (timer) clearInterval(timer);
            if (map) map.destroy();
            if (host && host.parentNode) host.parentNode.removeChild(host);
          }
        };
      }
    });
  };
};
