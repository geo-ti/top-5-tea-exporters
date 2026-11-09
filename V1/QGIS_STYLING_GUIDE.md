# Day 13 QGIS styling guide - Defying Distance

`build_qgis_project.py` builds everything below automatically:

```
QT_QPA_PLATFORM=offscreen /Applications/QGIS.app/Contents/MacOS/python build_qgis_project.py
```

Outputs: `day13_defying_distance.qgz` (project with the "Defying Distance" layout) and `day13_defying_distance.png` (300 dpi).

## Project
- CRS: EPSG:4326 (plate carree). Map extent -180 to 180 lon, -60 to 75 lat.
- Background and page colour: `#13151A`.
- Page: A4 landscape (297 x 210 mm).

## Layers (`tea_gravity_interactions_day13.gpkg`), top to bottom
| Layer | Style |
|---|---|
| `country_nodes` | Categorized on `role`: exporter / both = `#F59E0B` circle 2.0 mm, importer = `#38BDF8` circle 1.5 mm, 0.2 mm `#13151A` outline. Labels: exporters plus PAK, IRQ, RUS, MAR, ARE, IRN, GBR, USA, EGY, coloured by role, with a 0.6 mm dark buffer |
| `trade_interaction_arcs` | Graduated on `Surplus_Centered` (see below). Stroke width data-defined from `line_width_mm`. Feature order: `line_width_mm` ascending, so the wide arcs draw on top |
| `world_basemap` | Fill `#1F232B`, border `#2D333F` 0.2 mm |

## Arc classes (`Surplus_Centered`, log10 units, 0 = median corridor)
| Range | Colour | Meaning |
|---|---|---|
| >= 1.25 | `#C026D3` + outer glow | Far above gravity (18x+) |
| 0.5 to 1.25 | `#E879F9` + outer glow | Above gravity (3-18x) |
| -0.5 to 0.5 | `#F59E0B` | Close to gravity |
| < -0.5 | `#475569`, 40% opacity | Below gravity (high friction) |

Outer glow (anomaly classes only): spread 1.2 mm, blur 2, opacity 40%, same colour as the line.

## Layout
- Title `DEFYING DISTANCE` (Baloo Bhaijaan bold, 10 mm), subtitle in Baloo Bhai 2.
- Badge (top right): `#30DayMapChallenge 2026 • Day 13: Interactions`, fuchsia outline.
- Gravity formula text box in the South Pacific.
- Numbered badges (1-3) 80% of the way along the three focus arcs, matching three callout cards along the bottom: Kenya -> Pakistan, Sri Lanka -> Iraq & Russia, China -> Morocco. Card figures are read from the data at build time.
- Legend (bottom left): surplus classes, line widths for 10k / 50k / 200k tonnes, and exporter/importer dots.
- Footer: data sources, credit and disclaimer in Arial Narrow.
