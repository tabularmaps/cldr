# design/

Human design inputs that constrain the optimizer. Nothing here is
generated; every file is a reviewed, reasoned choice recorded in
`DECISIONS.md`.

## Territory maps (`territories-<W>x<H>.txt`)

Optional. A text picture of the grid, one character per cell, that tells
`scripts/optimize_layout.py --territories` which cells each subregion may
occupy. Header lines map a letter to CLDR subregion codes (or individual
identifiers):

```text
# N=021          Northern America
# C=013,029      Central America, Caribbean
# .              fixed blank
# *              any identifier
NNNNNEEEEEEEEE...
```

Identifiers whose subregion is not mentioned are unconstrained. This is the
two-stage method used by the sibling project `tabularmaps/do` (hand-drawn
territories, optimized interiors). The initial release did not use a
territory map for the selected board so that every grid candidate was
optimized under identical, purely automatic conditions; see
`OPTIMIZATION.md`.

## Pins

`--pins '{"JP": [18, 3]}'` fixes identifiers to cells. Every pin used for a
committed board must have a reason in `DECISIONS.md`, and the before/after
scores must be reported.
