"""
Day 13 (Interactions) - download the input data.

Run in the conda env:  conda run -n map2026 python procure_data_day13.py

Outputs (in ./data):
  gdp_wb.csv                 World Bank GDP, current USD (NY.GDP.MKTP.CD)
  raw/ne_110m_admin_0_countries/   Natural Earth 1:110m countries
  tea_bilateral_trade.csv    UN Comtrade HS 0902 exports by partner, 5 origins
"""
import io
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "raw"
RAW.mkdir(parents=True, exist_ok=True)

GDP_YEAR = 2023
TRADE_YEAR = 2024
# Top tea exporters: UN M49 reporter codes used by Comtrade
ORIGINS = {"KEN": 404, "CHN": 156, "LKA": 144, "IND": 699, "VNM": 704}


def get_with_retry(url, params=None, tries=6, wait=8):
    """GET a URL, waiting and retrying when the server rate-limits us."""
    for attempt in range(tries):
        r = requests.get(url, params=params, timeout=120)
        if r.status_code == 200:
            return r
        print(f"  HTTP {r.status_code}, retrying in {wait}s ...")
        time.sleep(wait)
    r.raise_for_status()


def download_gdp():
    """World Bank GDP (current USD) for every country."""
    url = "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.MKTP.CD"
    rows = get_with_retry(url, {"date": GDP_YEAR, "format": "json", "per_page": 400}).json()[1]
    df = pd.DataFrame({
        "ISO3": [r["countryiso3code"] for r in rows],
        "Country": [r["country"]["value"] for r in rows],
        "GDP_USD": [r["value"] for r in rows],
    })
    # Aggregates (World, regions, income groups) are dropped later by joining
    # on Natural Earth countries; here we just drop empty rows.
    df = df[(df["ISO3"] != "") & df["GDP_USD"].notna()]
    df.to_csv(DATA / "gdp_wb.csv", index=False)
    print(f"GDP: {len(df)} rows -> data/gdp_wb.csv")


def download_natural_earth():
    out = RAW / "ne_110m_admin_0_countries"
    if out.exists():
        print("Natural Earth 110m already downloaded")
        return
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    r = get_with_retry(url)
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(out)
    print(f"Natural Earth -> {out.relative_to(HERE)}")


def download_trade():
    """Tea (HS 0902) exports by partner from the UN Comtrade public preview API."""
    url = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
    frames = []
    for iso3, code in ORIGINS.items():
        # Use the latest year; some countries have not reported it yet, so fall back a year
        for year in (TRADE_YEAR, TRADE_YEAR - 1):
            params = {"reporterCode": code, "period": year, "cmdCode": "0902", "flowCode": "X"}
            data = get_with_retry(url, params).json()["data"]
            time.sleep(6)  # be gentle with the public API
            if data:
                break
        if not data:
            raise RuntimeError(f"No Comtrade data for {iso3}; download it manually from WITS")
        df = pd.DataFrame(data)
        # Keep the plain partner totals (no second partner, all customs, all transport modes)
        df = df[(df["partner2Code"] == 0) & (df["customsCode"] == "C00") & (df["motCode"] == 0)]
        df = df[df["partnerCode"] != 0]  # 0 = World
        frames.append(pd.DataFrame({
            "origin_iso3": iso3,
            "year": year,
            "partner_m49": df["partnerCode"],
            "tonnes": df["netWgt"] / 1000,
            "value_usd": df["primaryValue"],
        }))
        print(f"Comtrade {iso3} {year}: {len(df)} partners")

    trade = pd.concat(frames, ignore_index=True)

    # Partner M49 code -> ISO3 using the Comtrade reference list
    ref = get_with_retry("https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json").json()["results"]
    m49_to_iso = {r["id"]: r["PartnerCodeIsoAlpha3"] for r in ref}
    trade["dest_iso3"] = trade["partner_m49"].map(m49_to_iso)

    trade = trade[["origin_iso3", "year", "dest_iso3", "partner_m49", "tonnes", "value_usd"]]
    trade.to_csv(DATA / "tea_bilateral_trade.csv", index=False)
    print(f"Trade: {len(trade)} corridors -> data/tea_bilateral_trade.csv")


if __name__ == "__main__":
    download_gdp()
    download_natural_earth()
    download_trade()
