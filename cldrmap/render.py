"""SVG preview of a layout: equal square cells, subregion colours, labels."""

from __future__ import annotations

from xml.sax.saxutils import escape

from .board import Layout
from .geo import GeoInputs

# CLDR/M49 subregion -> colour family (informational; not part of the data contract)
PALETTE = {
    "021": "#6c8ebf", "013": "#7f9ccf", "029": "#93a9d9", "005": "#5f7fb5",      # Americas: blues
    "154": "#c76b6b", "155": "#d17f7f", "151": "#b85c5c", "039": "#d99191",      # Europe: reds
    "015": "#d9a441", "011": "#e0b35a", "017": "#c99a3a", "014": "#e6c27a", "018": "#bf8f2e",  # Africa: yellows
    "145": "#7fb37f", "143": "#6aa36a", "034": "#8fc08f", "035": "#a3cda3", "030": "#5e955e",  # Asia: greens
    "053": "#a67fc7", "054": "#b592d1", "057": "#c4a6db", "061": "#d2bae5",      # Oceania: purples
    None: "#bdbdbd",
}


def render_svg(layout: Layout, geo: GeoInputs, cell: int = 36, gap: int = 2, margin: int = 12, title: str | None = None, dim: set[str] | None = None) -> str:
    """Render the board. ``dim`` is an optional set of identifiers drawn as
    faint outlines (position kept, colour and label muted); everything else
    is drawn normally."""
    w = layout.width * (cell + gap) - gap + 2 * margin
    h = layout.height * (cell + gap) - gap + 2 * margin + (28 if title else 0)
    top = margin + (28 if title else 0)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="ui-monospace, Menlo, monospace">',
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    if title:
        out.append(f'<text x="{margin}" y="{margin + 14}" font-size="14" fill="#333">{escape(title)}</text>')
    for y in range(layout.height):
        for x in range(layout.width):
            px, py = margin + x * (cell + gap), top + y * (cell + gap)
            out.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" fill="#f3f3f3" stroke="none"/>')
    for cid, (x, y) in layout.cells.items():
        i = geo.index[cid]
        color = PALETTE.get(geo.subregion[i], PALETTE[None])
        px, py = margin + x * (cell + gap), top + y * (cell + gap)
        if dim and cid in dim:
            out.append(f'<g><title>{cid} {escape(geo.names[i])}</title><rect x="{px + 0.5}" y="{py + 0.5}" width="{cell - 1}" height="{cell - 1}" fill="#ffffff" stroke="{color}" stroke-width="1" rx="3"/>'
                       f'<text x="{px + cell / 2}" y="{py + cell / 2 + 5}" font-size="{cell * 0.38:.0f}" text-anchor="middle" fill="#b0b0b0">{cid}</text></g>')
            continue
        out.append(f'<g><title>{cid} {escape(geo.names[i])}</title><rect x="{px}" y="{py}" width="{cell}" height="{cell}" fill="{color}" rx="3"/>'
                   f'<text x="{px + cell / 2}" y="{py + cell / 2 + 5}" font-size="{cell * 0.38:.0f}" text-anchor="middle" fill="#111">{cid}</text></g>')
    out.append("</svg>")
    return "\n".join(out)
