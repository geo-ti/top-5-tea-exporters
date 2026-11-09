"""
Day 13 (Interactions) - interactive "Follow the Tea" web map.

Run in the conda env:  conda run -n map2026 python build_interactive_map.py
Needs ../data/tea_bilateral_trade.csv (from ../procure_data_day13.py).

Reads interactive_template.html, fills in the data as JSON and writes
day13_follow_the_tea.html (a single self-contained page, deck.gl from a CDN).
Coordinates stay in plain lon/lat (EPSG:4326); the page uses a flat
orthographic view, so the map is drawn as plate carree.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"        # shared Day13/data

DATA_CSV = DATA / "tea_bilateral_trade.csv"
NE_110 = DATA / "raw/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
NE_50 = DATA / "inputs/ne_50m_admin_0_countries"   # includes small partners (Singapore, Bahrain...)
INDIA = DATA / "inputs/india_global.gpkg"
TEMPLATE = HERE / "interactive_template.html"
OUT = HERE / "day13_follow_the_tea.html"

# Comtrade "Other Asia, nes" (S19) is the code used for Taiwan
PARTNER_FIX = {"S19": "TWN"}
EXPORTER_ORDER = ["KEN", "CHN", "IND", "LKA", "VNM"]   # by export volume = colour slot order


def load_countries(path):
    """Natural Earth countries with an ISO3 key, and the India boundary swapped in."""
    ne = gpd.read_file(path).to_crs("EPSG:4326")
    # ISO_A3_EH is -99 for a few places; fall back to ADM0_A3
    ne["ISO3"] = ne["ISO_A3_EH"].where(ne["ISO_A3_EH"] != "-99", ne["ADM0_A3"])
    ne = ne[["ISO3", "NAME", "geometry"]]

    india_geom = gpd.read_file(INDIA).to_crs("EPSG:4326").union_all()
    ne = ne[ne["ISO3"] != "IND"].copy()
    touches = ne.intersects(india_geom)
    ne.loc[touches, "geometry"] = ne.loc[touches, "geometry"].difference(india_geom)
    india = gpd.GeoDataFrame({"ISO3": ["IND"], "NAME": ["India"]}, geometry=[india_geom], crs="EPSG:4326")
    return pd.concat([ne, india], ignore_index=True)


def bezier_arc(x0, y0, x1, y1, bend=0.15, n=40, max_lat=68.0):
    """Quadratic Bezier curve in lon/lat, bent sideways by `bend` x chord length."""
    dx, dy = x1 - x0, y1 - y0
    # Control point: chord midpoint pushed out along the left-hand normal
    cx = (x0 + x1) / 2 - dy * bend
    cy = (y0 + y1) / 2 + dx * bend
    t = np.linspace(0, 1, n)
    xs = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
    ys = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
    ys = np.minimum(ys, max_lat)   # keep arcs out of the far north
    return LineString(zip(xs, ys))


def round_coords(geom, ndigits=2):
    """GeoJSON geometry dict with coordinates rounded, to keep the page small."""
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(v, ndigits) for v in c]
    g = geom.__geo_interface__
    return {"type": g["type"], "coordinates": rnd(g["coordinates"])}


def main():
    trade = pd.read_csv(DATA_CSV)
    trade["dest_iso3"] = trade["dest_iso3"].str.strip().replace(PARTNER_FIX)
    trade = trade[trade["tonnes"] > 0]

    # One representative point per country (1:50m, so small partners are included)
    pts = load_countries(NE_50).dissolve("ISO3", aggfunc="first")
    pts["geometry"] = pts.geometry.representative_point()
    trade = trade[trade["dest_iso3"].isin(pts.index)].copy()   # drops unallocated codes

    # --- countries (basemap polygons) ---------------------------------------
    world = load_countries(NE_110)
    world["geometry"] = world.geometry.simplify(0.05)
    countries = [
        {"type": "Feature", "properties": {"iso": r.ISO3, "name": r.NAME},
         "geometry": round_coords(r.geometry)}
        for r in world.itertuples() if r.ISO3 != "ATA"
    ]

    # --- places: every country that appears in the trade data ---------------
    used = sorted(set(trade["origin_iso3"]) | set(trade["dest_iso3"]))
    places = {
        iso: {"name": pts.loc[iso, "NAME"],
              "lon": round(pts.loc[iso, "geometry"].x, 2),
              "lat": round(pts.loc[iso, "geometry"].y, 2)}
        for iso in used
    }

    # --- flows: one curved path per corridor ---------------------------------
    flows = []
    for r in trade.sort_values("tonnes").itertuples():
        o, d = places[r.origin_iso3], places[r.dest_iso3]
        arc = bezier_arc(o["lon"], o["lat"], d["lon"], d["lat"], bend=0.15, n=40)
        flows.append({
            "o": r.origin_iso3, "d": r.dest_iso3, "year": int(r.year),
            "t": round(r.tonnes, 1), "usd": round(r.value_usd),
            "path": [[round(x, 2), round(y, 2)] for x, y in arc.coords],
        })

    data = {"exporters": EXPORTER_ORDER, "places": places,
            "countries": {"type": "FeatureCollection", "features": countries},
            "flows": flows}
    html = TEMPLATE.read_text().replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUT.write_text(html)
    print(f"Wrote {OUT.name}: {len(flows)} flows, {len(places)} places, "
          f"{len(countries)} countries, {OUT.stat().st_size / 1e6:.1f} MB")



if __name__ == "__main__":
    main()
