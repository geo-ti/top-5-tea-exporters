"""
Day 13 (Interactions) - gravity model of the bilateral tea trade.

Run in the conda env:  conda run -n map2026 python compute_gravity_interactions.py
Needs the outputs of procure_data_day13.py.

  Expected_Score = (Prod_i / max Prod) * (GDP_j / max GDP) / (D_ij / 1000 km) ** 1.2
  Interaction_Ratio = actual tonnes / Expected_Score
  Log_Interaction_Surplus = log10(Interaction_Ratio + 1e-4)
  Surplus_Centered = Log_Interaction_Surplus - median  (0 = a typical corridor)

Output: tea_gravity_interactions_day13.gpkg (EPSG:4326) with layers
  trade_interaction_arcs, country_nodes, world_basemap
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"        # shared Day13/data (from procure_data_day13.py)

GPKG = HERE / "tea_gravity_interactions_day13.gpkg"

NE_110 = DATA / "raw/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
NE_50 = DATA / "inputs/ne_50m_admin_0_countries"   # more small countries (Singapore, Bahrain...)
INDIA = DATA / "inputs/india_global.gpkg"
FAOSTAT = DATA / "inputs/FAOSTAT_data_en_11-9-2026.csv"

BETA = 1.2
TOP_N = 15          # partners kept per origin
MAX_LAT = 68.0      # arcs are clipped below this latitude
# FAOSTAT M49 area codes for the origins (China, mainland = 156; India = 356)
FAO_CODES = {"KEN": 404, "CHN": 156, "LKA": 144, "IND": 356, "VNM": 704}


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


def haversine_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def bezier_arc(x0, y0, x1, y1, bend=0.2, n=50):
    """Quadratic Bezier curve in lon/lat, bent sideways by `bend` x chord length."""
    dx, dy = x1 - x0, y1 - y0
    # Control point: chord midpoint pushed out along the left-hand normal
    cx = (x0 + x1) / 2 - dy * bend
    cy = (y0 + y1) / 2 + dx * bend
    t = np.linspace(0, 1, n)
    xs = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
    ys = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
    ys = np.minimum(ys, MAX_LAT)   # keep arcs out of the far north
    return LineString(zip(xs, ys))


def main():
    # --- inputs -------------------------------------------------------------
    trade = pd.read_csv(DATA / "tea_bilateral_trade.csv")
    gdp = pd.read_csv(DATA / "gdp_wb.csv")[["ISO3", "GDP_USD"]]

    fao = pd.read_csv(FAOSTAT, encoding="utf-8-sig")
    fao = fao[fao["Item"] == "Tea leaves"]
    code_to_iso = {v: k for k, v in FAO_CODES.items()}
    fao["ISO3"] = fao["Area Code (M49)"].astype(int).map(code_to_iso)
    prod = fao.dropna(subset=["ISO3"]).set_index("ISO3")["Value"].rename("prod_t")

    # Representative points from the 50m countries (covers small trade partners)
    ne50 = load_countries(NE_50)
    pts = ne50.dissolve("ISO3", aggfunc="first")   # one shape per ISO3
    pts["geometry"] = pts.geometry.representative_point()
    pts["lon"], pts["lat"] = pts.geometry.x, pts.geometry.y

    # --- corridors ----------------------------------------------------------
    df = trade[trade["tonnes"] > 0].copy()
    df = df.merge(gdp, left_on="dest_iso3", right_on="ISO3", how="inner").drop(columns="ISO3")
    df = df[df["dest_iso3"].isin(pts.index)]
    # Keep each origin's largest partners
    df = df.sort_values("tonnes", ascending=False).groupby("origin_iso3").head(TOP_N).copy()

    df["prod_t"] = df["origin_iso3"].map(prod)
    df["origin_name"] = df["origin_iso3"].map(pts["NAME"])
    df["dest_name"] = df["dest_iso3"].map(pts["NAME"])
    o = pts.loc[df["origin_iso3"], ["lon", "lat"]].to_numpy()
    d = pts.loc[df["dest_iso3"], ["lon", "lat"]].to_numpy()
    df["distance_km"] = haversine_km(o[:, 0], o[:, 1], d[:, 0], d[:, 1])

    # --- gravity model ------------------------------------------------------
    df["Expected_Score"] = (
        (df["prod_t"] / df["prod_t"].max()) * (df["GDP_USD"] / df["GDP_USD"].max())
        / (df["distance_km"] / 1000) ** BETA
    )
    df["Interaction_Ratio"] = df["tonnes"] / df["Expected_Score"]
    df["Log_Interaction_Surplus"] = np.log10(df["Interaction_Ratio"] + 1e-4)
    df["Surplus_Centered"] = df["Log_Interaction_Surplus"] - df["Log_Interaction_Surplus"].median()
    df["line_width_mm"] = 0.3 + 2.8 * np.sqrt(df["tonnes"] / df["tonnes"].max())

    arcs = gpd.GeoDataFrame(
        df.round(4),
        geometry=[bezier_arc(a[0], a[1], b[0], b[1]) for a, b in zip(o, d)],
        crs="EPSG:4326",
    ).sort_values("line_width_mm")   # thin arcs first, so wide arcs draw on top

    # --- nodes --------------------------------------------------------------
    origins = set(df["origin_iso3"])
    dests = set(df["dest_iso3"])
    nodes = pts.loc[sorted(origins | dests), ["NAME", "geometry"]].reset_index()
    nodes["role"] = np.where(nodes["ISO3"].isin(origins),
                             np.where(nodes["ISO3"].isin(dests), "both", "exporter"), "importer")
    nodes["export_t"] = nodes["ISO3"].map(df.groupby("origin_iso3")["tonnes"].sum()).fillna(0).round(1)
    nodes["import_t"] = nodes["ISO3"].map(df.groupby("dest_iso3")["tonnes"].sum()).fillna(0).round(1)

    # --- basemap ------------------------------------------------------------
    world = load_countries(NE_110)

    # --- write --------------------------------------------------------------
    GPKG.unlink(missing_ok=True)
    arcs.to_file(GPKG, layer="trade_interaction_arcs", driver="GPKG")
    nodes.to_file(GPKG, layer="country_nodes", driver="GPKG")
    world.to_file(GPKG, layer="world_basemap", driver="GPKG")
    print(f"Wrote {GPKG.name}: {len(arcs)} arcs, {len(nodes)} nodes, {len(world)} countries")

    cols = ["origin_iso3", "dest_iso3", "tonnes", "distance_km", "Surplus_Centered"]
    ranked = arcs.sort_values("Surplus_Centered", ascending=False)[cols]
    print("\nTop 12 interaction surpluses:\n", ranked.head(12).to_string(index=False))
    print("\nBottom 8:\n", ranked.tail(8).to_string(index=False))
    focus = [("KEN", "PAK"), ("LKA", "IRQ"), ("LKA", "RUS"), ("CHN", "MAR"), ("IND", "IRN"), ("IND", "ARE")]
    sel = ranked[[(a, b) in focus for a, b in zip(ranked.origin_iso3, ranked.dest_iso3)]]
    print("\nFocus corridors:\n", sel.to_string(index=False))


if __name__ == "__main__":
    main()
