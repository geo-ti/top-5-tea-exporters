"""
Day 13 (Interactions) - build the styled QGIS project and print layout.
Dark theme from claude_ins.md, plain lat/long (EPSG:4326).

Uses PyQGIS, so run it with the Python that ships with QGIS (not the conda env):
    QT_QPA_PLATFORM=offscreen /Applications/QGIS.app/Contents/MacOS/python build_qgis_project.py

Needs tea_gravity_interactions_day13.gpkg (run compute_gravity_interactions.py first).
Outputs: day13_defying_distance.qgz and day13_defying_distance.png (layout export).
"""
import os
from pathlib import Path

QGIS_APP = Path("/Applications/QGIS.app/Contents")
os.environ.setdefault("PROJ_DATA", str(QGIS_APP / "Resources/qgis/proj"))

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem,
    QgsEffectStack, QgsDrawSourceEffect, QgsFeatureRequest, QgsFillSymbol,
    QgsGraduatedSymbolRenderer, QgsLayoutExporter, QgsLayoutItemLabel, QgsLayoutItemMap,
    QgsLayoutItemPolyline, QgsLayoutItemShape, QgsLayoutMeasurement, QgsLayoutPoint, QgsLayoutSize, QgsLineSymbol,
    QgsMarkerSymbol, QgsOuterGlowEffect, QgsPalLayerSettings, QgsPrintLayout, QgsProject,
    QgsProperty, QgsRectangle, QgsRendererCategory, QgsRendererRange, QgsSingleSymbolRenderer,
    QgsTextBufferSettings, QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QPointF, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QFont, QPolygonF  # noqa: E402

HERE = Path(__file__).resolve().parent
GPKG = HERE / "tea_gravity_interactions_day13.gpkg"
QGZ = HERE / "day13_defying_distance.qgz"
PNG = HERE / "day13_defying_distance.png"
LAYOUT_NAME = "Defying Distance"
CRS = QgsCoordinateReferenceSystem("EPSG:4326")

# Palette from claude_ins.md
OCEAN = "#13151A"
LAND = "#1F232B"
BORDER = "#2D333F"
AMBER = "#F59E0B"
CYAN = "#38BDF8"
FUCHSIA_LIGHT = "#E879F9"
FUCHSIA_DEEP = "#C026D3"
SLATE = "#475569"
TEXT = "#E5E7EB"
MUTED = "#94A3B8"
TITLE_FONT = "Baloo Bhaijaan"
SUB_FONT = "Baloo Bhai 2"
FOOT_FONT = "Arial Narrow"

# Surplus classes on Surplus_Centered (log10 units, 0 = median corridor)
CLASSES = [
    (-9, -0.5, SLATE, 0.4, "Below gravity (high friction)"),
    (-0.5, 0.5, AMBER, 1.0, "Close to gravity"),
    (0.5, 1.25, FUCHSIA_LIGHT, 1.0, "Above gravity (3-18x)"),
    (1.25, 9, FUCHSIA_DEEP, 1.0, "Far above gravity (18x+)"),
]

# Page (A4 landscape) and map frame; map aspect matches the extent (360 x 135 deg)
PW, PH = 297, 210
EXTENT = QgsRectangle(-180, -60, 180, 75)
MAP_X, MAP_Y, MAP_W = 0, 27, 297
MAP_H = MAP_W * EXTENT.height() / EXTENT.width()

LABELLED = ("PAK", "IRQ", "RUS", "MAR", "ARE", "IRN", "GBR", "USA", "EGY")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def to_page(lon, lat):
    """Longitude/latitude -> layout millimetres."""
    x = MAP_X + (lon - EXTENT.xMinimum()) / EXTENT.width() * MAP_W
    y = MAP_Y + (EXTENT.yMaximum() - lat) / EXTENT.height() * MAP_H
    return x, y


def text_format(size_mm, color=TEXT, family=SUB_FONT, bold=False, italic=False):
    font = QFont(family)
    font.setBold(bold)
    font.setItalic(italic)
    fmt = QgsTextFormat()
    fmt.setFont(font)
    fmt.setSize(size_mm)
    fmt.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setColor(QColor(color))
    return fmt


def load_layer(name, title):
    layer = QgsVectorLayer(f"{GPKG}|layername={name}", title, "ogr")
    assert layer.isValid(), f"Could not load layer {name}"
    return layer


def corridor_info(arcs):
    """{(origin, dest): (badge lon, lat, tonnes, km, surplus)} for every arc.
    The badge point sits 80% of the way along the arc, near the importer."""
    out = {}
    for f in arcs.getFeatures():
        mid = f.geometry().interpolate(f.geometry().length() * 0.8).asPoint()
        out[(f["origin_iso3"], f["dest_iso3"])] = (
            mid.x(), mid.y(), f["tonnes"], f["distance_km"], f["Surplus_Centered"])
    return out


# ---------------------------------------------------------------------------
# Layer styling
# ---------------------------------------------------------------------------
def style_basemap(layer):
    layer.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
        {"color": LAND, "outline_color": BORDER, "outline_width": "0.2"})))


def glow_effect(color):
    """Soft outer glow so the anomaly corridors read as light on the dark map."""
    glow = QgsOuterGlowEffect()
    glow.setSpread(1.2)
    glow.setSpreadUnit(Qgis.RenderUnit.Millimeters)
    glow.setBlurLevel(2)
    glow.setOpacity(0.4)
    glow.setColorType(QgsOuterGlowEffect.GlowColorType.SingleColor)
    glow.setColor(QColor(color))
    stack = QgsEffectStack()
    stack.appendEffect(glow)
    stack.appendEffect(QgsDrawSourceEffect())
    return stack


def style_arcs(layer):
    ranges = []
    for lo, hi, color, opacity, label in CLASSES:
        sym = QgsLineSymbol.createSimple({"line_color": color, "capstyle": "round"})
        sym.setOpacity(opacity)
        # Width comes from the data: 0.3 + 2.8 * sqrt(tonnes / max tonnes)
        sym.setDataDefinedWidth(QgsProperty.fromField("line_width_mm"))
        if color in (FUCHSIA_LIGHT, FUCHSIA_DEEP):
            sym.symbolLayer(0).setPaintEffect(glow_effect(color))
        ranges.append(QgsRendererRange(lo, hi, sym, label))
    renderer = QgsGraduatedSymbolRenderer("Surplus_Centered", ranges)

    # Thin arcs first, so the widest corridors sit on top
    renderer.setOrderBy(QgsFeatureRequest.OrderBy(
        [QgsFeatureRequest.OrderByClause("line_width_mm", True)]))
    renderer.setOrderByEnabled(True)
    layer.setRenderer(renderer)


def style_nodes(layer):
    def dot(color, size):
        return QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": color, "size": str(size),
             "outline_color": OCEAN, "outline_width": "0.2"})
    cats = [
        QgsRendererCategory("importer", dot(CYAN, 1.5), "Importer"),
        QgsRendererCategory("exporter", dot(AMBER, 2.0), "Exporter"),
        QgsRendererCategory("both", dot(AMBER, 2.0), "Exporter (also imports)"),
    ]
    renderer = QgsCategorizedSymbolRenderer("role", cats)
    # Draw importers first, exporters on top
    renderer.setOrderBy(QgsFeatureRequest.OrderBy(
        [QgsFeatureRequest.OrderByClause("\"role\" = 'importer'", False)]))
    renderer.setOrderByEnabled(True)
    layer.setRenderer(renderer)

    # Labels: all exporters and a few key importers
    pal = QgsPalLayerSettings()
    iso_list = ", ".join(f"'{c}'" for c in LABELLED)
    pal.fieldName = f"CASE WHEN \"role\" <> 'importer' OR \"ISO3\" IN ({iso_list}) THEN \"NAME\" END"
    pal.isExpression = True
    fmt = text_format(2.6, TEXT, SUB_FONT)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(0.6)
    buf.setColor(QColor(OCEAN))
    fmt.setBuffer(buf)
    pal.setFormat(fmt)
    pal.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    pal.dist = 0.8
    pal.dataDefinedProperties().setProperty(
        QgsPalLayerSettings.Property.Color,
        QgsProperty.fromExpression(f"CASE WHEN \"role\" = 'importer' THEN '{CYAN}' ELSE '{AMBER}' END"))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


# ---------------------------------------------------------------------------
# Layout items
# ---------------------------------------------------------------------------
def add_label(layout, text, x, y, w, h, fmt, halign=Qt.AlignmentFlag.AlignLeft,
              valign=Qt.AlignmentFlag.AlignTop):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setTextFormat(fmt)
    item.setHAlign(halign)
    item.setVAlign(valign)
    item.setMarginX(0)
    item.setMarginY(0)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(w, h))
    return item


def add_shape(layout, x, y, w, h, fill, stroke, width=0.3, ellipse=False, radius=0):
    shape = QgsLayoutItemShape(layout)
    shape.setShapeType(QgsLayoutItemShape.Shape.Ellipse if ellipse
                       else QgsLayoutItemShape.Shape.Rectangle)
    if radius:
        shape.setCornerRadius(QgsLayoutMeasurement(radius))
    shape.setSymbol(QgsFillSymbol.createSimple(
        {"color": fill, "outline_color": stroke, "outline_width": str(width)}))
    layout.addLayoutItem(shape)
    shape.attemptMove(QgsLayoutPoint(x, y))
    shape.attemptResize(QgsLayoutSize(w, h))
    return shape


def add_line(layout, points, color, width, opacity=1.0):
    line = QgsLayoutItemPolyline(QPolygonF([QPointF(x, y) for x, y in points]), layout)
    sym = QgsLineSymbol.createSimple({"line_color": color, "line_width": str(width),
                                      "capstyle": "round"})
    sym.setOpacity(opacity)
    line.setSymbol(sym)
    layout.addLayoutItem(line)
    return line


def add_badge(layout, number, x, y, d=4.2):
    """Numbered circle centred on (x, y) in layout mm."""
    add_shape(layout, x - d / 2, y - d / 2, d, d, OCEAN, TEXT, 0.3, ellipse=True)
    add_label(layout, str(number), x - d / 2, y - d / 2 + 0.1, d, d,
              text_format(2.8, TEXT, SUB_FONT, bold=True),
              Qt.AlignmentFlag.AlignHCenter, Qt.AlignmentFlag.AlignVCenter)


def add_card(layout, number, title, body, x, y, w=68, h=37):
    add_shape(layout, x, y, w, h, "#181B21", BORDER, 0.3)
    add_shape(layout, x, y, 1.2, h, FUCHSIA_DEEP, FUCHSIA_DEEP, 0)   # accent bar
    add_badge(layout, number, x + 6, y + 5.6)
    add_label(layout, title, x + 10, y + 2.6, w - 12, 7,
              text_format(4.0, FUCHSIA_LIGHT, TITLE_FONT, bold=True))
    add_label(layout, body, x + 4, y + 11, w - 7, h - 12, text_format(2.9, TEXT, SUB_FONT))


def add_legend(layout, x, y, max_t):
    add_label(layout, "Interaction surplus", x, y, 70, 6, text_format(4.0, TEXT, TITLE_FONT, bold=True))
    add_label(layout, "Actual trade vs gravity expectation,\nrelative to the median corridor",
              x, y + 6, 70, 8, text_format(2.6, MUTED, SUB_FONT))
    for i, (_, _, color, opacity, label) in enumerate(reversed(CLASSES)):
        yy = y + 17 + i * 5
        add_line(layout, [(x, yy), (x + 10, yy)], color, 1.4, opacity)
        add_label(layout, label, x + 13, yy - 1.8, 55, 4, text_format(2.8, TEXT, SUB_FONT))

    yy = y + 40
    add_label(layout, "Volume (tonnes)", x, yy - 3, 50, 4, text_format(2.8, MUTED, SUB_FONT))
    for i, t in enumerate((10_000, 50_000, 200_000)):
        width = 0.3 + 2.8 * (t / max_t) ** 0.5
        xx = x + i * 24
        add_line(layout, [(xx, yy + 4), (xx + 9, yy + 4)], AMBER, width)
        add_label(layout, f"{t // 1000}k", xx + 12, yy + 2.3, 10, 4, text_format(2.6, TEXT, SUB_FONT))

    add_label(layout, "Exporter", x + 4, yy + 8.5, 20, 4, text_format(2.6, TEXT, SUB_FONT))
    add_shape(layout, x, yy + 9, 2.0, 2.0, AMBER, OCEAN, 0.2, ellipse=True)
    add_label(layout, "Importer", x + 26, yy + 8.5, 20, 4, text_format(2.6, TEXT, SUB_FONT))
    add_shape(layout, x + 22.25, yy + 9.25, 1.5, 1.5, CYAN, OCEAN, 0.2, ellipse=True)


def fold(surplus):
    """Log10 surplus -> 'x times' the median corridor."""
    return 10 ** surplus


def build_layout(project, layers, info):
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(LAYOUT_NAME)
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(PW, PH))
    page.setPageStyleSymbol(QgsFillSymbol.createSimple({"color": OCEAN, "outline_style": "no"}))

    # --- Map -----------------------------------------------------------------
    map_item = QgsLayoutItemMap(layout)
    map_item.setCrs(CRS)
    map_item.setBackgroundColor(QColor(OCEAN))
    map_item.setFrameEnabled(False)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y))
    map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H))
    map_item.setExtent(EXTENT)
    map_item.setLayers([layers["nodes"], layers["arcs"], layers["world"]])
    map_item.setKeepLayerSet(True)

    # --- Titles --------------------------------------------------------------
    add_label(layout, "DEFYING DISTANCE", 8, 4, 200, 12,
              text_format(10, TEXT, TITLE_FONT, bold=True))
    add_label(layout, "Bilateral Gravity Interactions & Spatial Anomalies in the Global Tea Trade",
              8, 15.5, 220, 7, text_format(4.6, MUTED, SUB_FONT))
    add_shape(layout, 212, 7, 78, 7.5, "#181B21", FUCHSIA_DEEP, 0.3)
    add_label(layout, "#30DayMapChallenge 2026 • Day 13: Interactions", 212, 7, 78, 7.5,
              text_format(3.0, FUCHSIA_LIGHT, SUB_FONT, bold=True),
              Qt.AlignmentFlag.AlignHCenter, Qt.AlignmentFlag.AlignVCenter)

    # --- Formula in the South Pacific ----------------------------------------
    fx, fy = to_page(-174, -2)
    add_label(layout, "The gravity model", fx, fy, 70, 5, text_format(3.4, TEXT, TITLE_FONT, bold=True))
    add_label(layout,
              "Expected(i,j) = (Prod i / max Prod) × (GDP j / max GDP)\n"
              "                        ÷ (Distance i,j / 1,000 km)^1.2\n\n"
              "Surplus = log10(Actual tonnes ÷ Expected)\n\n"
              "Big tea growers should sell most to rich, nearby\n"
              "markets. Purple corridors trade far more than\n"
              "production, GDP and distance alone would predict.",
              fx, fy + 5.5, 74, 30, text_format(2.6, MUTED, SUB_FONT))

    # --- Numbered badges on the focus corridors ------------------------------
    focus = [("KEN", "PAK"), ("LKA", "IRQ"), ("CHN", "MAR")]
    for n, key in enumerate(focus, start=1):
        lon, lat = info[key][:2]
        add_badge(layout, n, *to_page(lon, lat))

    # --- Bottom band: legend + three callout cards ---------------------------
    by = MAP_Y + MAP_H + 4
    max_t = max(v[2] for v in info.values())
    add_legend(layout, 8, by, max_t)

    kp, li, lr, cm = info[("KEN", "PAK")], info[("LKA", "IRQ")], info[("LKA", "RUS")], info[("CHN", "MAR")]
    add_card(layout, 1, "Kenya → Pakistan",
             f"{kp[2] / 1000:,.0f} thousand tonnes across {kp[3]:,.0f} km: the largest single tea "
             f"corridor on the map and about {fold(kp[4]):.0f}x the typical gravity ratio. "
             "Pakistan's everyday chai runs on Mombasa auction tea.",
             82, by)
    add_card(layout, 2, "Sri Lanka → Iraq & Russia",
             f"Ceylon orthodox tea goes to Iraq ({li[2] / 1000:,.0f}k t, about {fold(li[4]):.0f}x the "
             f"typical ratio) and Russia ({lr[2] / 1000:,.0f}k t, about {fold(lr[4]):.1f}x). "
             "Both far outrun what Sri Lanka's size and the distance predict.",
             153, by)
    add_card(layout, 3, "China → Morocco",
             f"{cm[2] / 1000:,.0f} thousand tonnes of green gunpowder tea across {cm[3]:,.0f} km, "
             f"about {fold(cm[4]):.0f}x the typical ratio. It keeps North Africa's mint tea going, "
             "and the same trail runs on to Mauritania, Senegal and The Gambia.",
             224, by, w=66)

    # --- Footer --------------------------------------------------------------
    add_label(layout, "Data: UN Comtrade, HS 0902 tea exports by partner (2024; Vietnam 2023); World Bank Open Data, "
                      "GDP current US$ (2023); UN FAOSTAT, tea leaf production (2024); Natural Earth (1:110m). "
                      "Top 15 partners per exporter.",
              8, PH - 12, 285, 4, text_format(2.8, MUTED, FOOT_FONT))
    add_label(layout, "Visualisation: Jyoti (@geo_tei) for #30DayMapChallenge 2026 | Day 13: Interactions",
              8, PH - 8.5, 285, 4, text_format(2.8, MUTED, FOOT_FONT))
    add_label(layout, "Map representation only for general illustration and does not necessarily reflect "
                      "the position of any country on international issues of recognition, sovereignty or jurisdiction.",
              8, PH - 5, 285, 4, text_format(2.6, MUTED, FOOT_FONT, italic=True))
    return layout


# ---------------------------------------------------------------------------
def main():
    project = QgsProject.instance()
    project.clear()
    project.setCrs(CRS)
    project.setBackgroundColor(QColor(OCEAN))
    project.setTitle("Day 13 Interactions - Defying Distance")

    layers = {
        "world": load_layer("world_basemap", "World basemap"),
        "arcs": load_layer("trade_interaction_arcs", "Tea trade interaction arcs"),
        "nodes": load_layer("country_nodes", "Country nodes"),
    }
    style_basemap(layers["world"])
    style_arcs(layers["arcs"])
    style_nodes(layers["nodes"])
    for key in ("world", "arcs", "nodes"):
        project.addMapLayer(layers[key])

    info = corridor_info(layers["arcs"])
    layout = build_layout(project, layers, info)
    project.layoutManager().addLayout(layout)
    project.write(str(QGZ))
    print(f"Wrote {QGZ}")

    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = 300
    result = QgsLayoutExporter(layout).exportToImage(str(PNG), settings)
    print(f"Export {'OK' if result == QgsLayoutExporter.ExportResult.Success else result}: {PNG}")


if __name__ == "__main__":
    QgsApplication.setPrefixPath(str(QGIS_APP / "MacOS"), True)
    app = QgsApplication([], False)
    app.initQgis()
    main()
    app.exitQgis()
