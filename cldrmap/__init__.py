"""CLDR Tabular Map: one identifier, one equal cell.

Library modules:

- ``mother_set``  extraction of the pinned CLDR regular-region set
- ``geo``         geographic inputs (representative points, adjacency, regions)
- ``board``       layout data contract, parsing, validation, board.csv
- ``scoring``     deterministic objective components
- ``optimize``    simulated-annealing search over a fixed grid
- ``baselines``   alphabetical, region-bucket, and legacy-derived layouts
- ``render``      SVG preview
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LAYOUTS = ROOT / "layouts"
