# Weight sensitivity (cldr-48.2-regular-2alpha-20x14.json, seed 1, 1500000 iterations per variant)

| variant | selected board scored under variant | re-optimized board under variant | re-optimized board under default weights | identifiers moved vs selected | mean Manhattan |
|---|---|---|---|---|---|
| default | 3.509 | 3.626 | 3.626 | 74% | 1.33 |
| neighborhood_half | 2.625 | 2.780 | 3.710 | 68% | 1.19 |
| neighborhood_double | 5.277 | 5.346 | 3.616 | 72% | 1.10 |
| global_half | 3.449 | 3.627 | 3.688 | 79% | 1.56 |
| global_double | 3.629 | 3.775 | 3.653 | 71% | 1.10 |
| adjacency_half | 3.028 | 3.091 | 3.638 | 63% | 1.01 |
| adjacency_double | 4.472 | 4.494 | 3.636 | 81% | 1.49 |
| direction_half | 3.404 | 3.485 | 3.648 | 79% | 1.44 |
| direction_double | 3.719 | 3.791 | 3.643 | 73% | 1.29 |
| region_half | 3.431 | 3.511 | 3.614 | 82% | 1.44 |
| region_double | 3.665 | 3.773 | 3.628 | 75% | 1.55 |
| false_adjacency_half | 3.371 | 3.506 | 3.674 | 70% | 1.16 |
| false_adjacency_double | 3.785 | 3.878 | 3.676 | 61% | 1.19 |
| whitespace_half | 3.501 | 3.726 | 3.742 | 74% | 1.21 |
| whitespace_double | 3.525 | 3.691 | 3.685 | 79% | 1.68 |
| legacy_1.0 | 4.469 | 4.622 | 3.626 | 74% | 1.33 |
