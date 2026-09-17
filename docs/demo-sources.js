/*
 * demo-sources.js — demo indicators (sources) for the dashboard.
 * Replace with your own fetchValues / valuesUrl in production.
 *
 * Latitude and longitude come from data/points.json (the representative points used for the
 * layout), so the colours double as a sanity check of the arrangement: north should read darker
 * towards the top, east darker towards the right.
 */
(function () {
  'use strict';
  let pointsPromise = null;
  function points() {
    if (!pointsPromise) pointsPromise = fetch('./data/points.json').then((r) => r.json());
    return pointsPromise;
  }
  function seriesFrom(label, unit, pick) {
    return points().then((pts) => {
      const values = {};
      for (const id in pts) values[id] = pick(pts[id]);
      return { label, unit, values, asOf: '(representative points, SOURCES.md)' };
    });
  }
  function pseudo(seed) {
    let x = seed >>> 0;
    return () => { x = (x * 1664525 + 1013904223) >>> 0; return x / 4294967296; };
  }
  window.TABULARMAPS_CLDR_DEMO_SOURCES = [
    { key: 'lat', name: 'Demo: latitude of representative point', fetchValues: () => seriesFrom('Latitude', '°N', (p) => p.lat) },
    { key: 'lon', name: 'Demo: longitude (unwrapped at 125°W)', fetchValues: () => seriesFrom('Longitude', '°E', (p) => (p.lon <= -125 ? p.lon + 360 : p.lon)) },
    {
      key: 'random', name: 'Demo: random values (5 s refresh)', refreshMs: 5000,
      fetchValues: () => points().then((pts) => {
        const rnd = pseudo(Math.floor(Date.now() / 5000));
        const values = {};
        for (const id in pts) values[id] = Math.round(rnd() * 1000) / 10;
        return { label: 'Random', unit: '%', min: 0, max: 100, values, asOf: new Date().toLocaleTimeString('en-GB') };
      })
    }
  ];
})();
