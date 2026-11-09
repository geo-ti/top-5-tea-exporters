# Day 13 data sources

| Data | Source | Notes |
|---|---|---|
| Bilateral tea exports, HS 0902, by partner | UN Comtrade public preview API: https://comtradeapi.un.org/public/v1/preview/C/A/HS (portal: https://comtradeplus.un.org) | Reporters Kenya, China, Sri Lanka, India (2024) and Vietnam (2023, because 2024 was not reported yet). Net weight in kg, converted to tonnes. Saved as `data/tea_bilateral_trade.csv` by `procure_data_day13.py`. Partner codes mapped to ISO3 with https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json |
| GDP, current US$ (NY.GDP.MKTP.CD), 2023 | World Bank Open Data API: https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD?date=2023&format=json&per_page=400 | `data/gdp_wb.csv`. Regional and income-group aggregates fall out when joined to countries |
| Tea leaf production, 2024 | UN FAOSTAT, Crops and livestock products (QCL): https://www.fao.org/faostat/en/#data/QCL | Copied from Day 12 to `data/inputs/FAOSTAT_data_en_11-9-2026.csv`. Fresh-leaf tonnes; China = "China, mainland" (M49 156) |
| Basemap countries | Natural Earth 1:110m Admin 0 Countries: https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip | Downloaded to `data/raw/` by `procure_data_day13.py` |
| Country points (representative points) | Natural Earth 1:50m Admin 0 Countries: https://www.naturalearthdata.com/downloads/50m-cultural-vectors/ | Copied to `data/inputs/ne_50m_admin_0_countries/`. Covers small partners missing at 110m (Hong Kong, Bahrain, Singapore...) |
| India boundary | `data/inputs/india_global.gpkg` (same layer as earlier days in the series) | Replaces Natural Earth India |

## Interactive map (`day13_follow_the_tea.html`)
- Built by `build_interactive_map.py` from `data/tea_bilateral_trade.csv` and `interactive_template.html`.
- All 580 exporter-partner corridors with recorded tonnage (no top-15 cut). Comtrade partner `S19` ("Other Asia, nes") is shown as Taiwan, the usual Comtrade convention. The unallocated codes `X1` and `_X` are dropped, which is why Kenya's total (609k t) is lower than its reported world total (626k t).
- Rendering: deck.gl 9.0.38 (https://deck.gl) from unpkg, using a flat orthographic view of lon/lat, so the map is plate carree (EPSG:4326).
- Exporter colours follow a validated categorical order (blue, orange, aqua, yellow, magenta). Orange and yellow are hard to tell apart with colour-vision deficiency, so every arc is also named in tooltips, labels and the side panel, and each exporter can be isolated with a click.

## Method notes (static gravity map)
- Gravity model: Expected = (Prod_i / max Prod) x (GDP_j / max GDP) / (D_ij / 1000 km)^1.2, with D_ij the Haversine distance between representative points.
- Surplus = log10(tonnes / Expected + 1e-4). The ratio has arbitrary units (tonnes per unitless score), so the map uses `Surplus_Centered` = surplus minus its median: 0 is a typical corridor, +1 is ten times the typical ratio.
- Only the top 15 partners per exporter (75 corridors) are kept.
- Check against the brief: Kenya->Pakistan (+1.79), Sri Lanka->Iraq (+1.33) and China->Morocco (+1.30) are strong anomalies. Sri Lanka->Russia is only moderately above typical (+0.41). India->Iran (-0.26) and India->UAE (+0.17) sit close to gravity, so they are not called out as anomalies.
