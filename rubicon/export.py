"""Export architecture diagrams as SVG.

Pure Python using xml.etree.ElementTree — no external dependencies.
"""

from __future__ import annotations

import logging
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import networkx as nx

from rubicon.models import RubiconConfig, Violation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SVG layout constants
# ---------------------------------------------------------------------------
_CANVAS_WIDTH = 800
_PADDING_X = 40
_PADDING_TOP = 60
_BAND_GAP = 8
_BAND_MIN_HEIGHT = 50
_BAND_MAX_HEIGHT = 120
_BAND_CORNER_RADIUS = 6
_FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
_TITLE_FONT_SIZE = 20
_LAYER_LABEL_FONT_SIZE = 14
_COUNT_FONT_SIZE = 12
_EDGE_LABEL_FONT_SIZE = 11
_LEGEND_FONT_SIZE = 11
_EDGE_AREA_WIDTH = 180
_LEGEND_HEIGHT = 50

_COLOR_CLEAN = "#50C878"
_COLOR_VIOLATION = "#D94A4A"
_COLOR_DEFAULT_LAYER = "#888888"
_COLOR_BG = "#FFFFFF"
_COLOR_TEXT_DARK = "#333333"
_COLOR_TEXT_LIGHT = "#FFFFFF"


def export_svg(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    *,
    width: int = _CANVAS_WIDTH,
) -> str:
    """Render the architecture layer diagram as an SVG string.

    Args:
        graph: The architecture graph with nodes containing 'layer' attributes.
        config: Rubicon configuration with layer definitions and colors.
        violations: List of detected rule violations.
        width: Canvas width in pixels. Defaults to 800.

    Returns:
        A complete SVG document as a string.
    """
    # Gather layer statistics
    layer_files: dict[str, int] = Counter()
    for node_id in graph.nodes:
        layer = graph.nodes[node_id].get("layer", "unclassified")
        layer_files[layer] += 1

    # Determine layer display order
    layers_to_show = _resolve_layer_order(config, layer_files)

    # Collect inter-layer edges
    layer_edges: dict[tuple[str, str], int] = Counter()
    for source_id, target_id, data in graph.edges(data=True):
        source_layer = graph.nodes[source_id].get("layer", "unclassified")
        target_layer = graph.nodes[target_id].get("layer", "unclassified")
        if source_layer != target_layer:
            rel_count = len(data.get("relationships", []))
            layer_edges[(source_layer, target_layer)] += rel_count

    # Collect violation edges
    violation_edges: dict[tuple[str, str], int] = Counter()
    for v in violations:
        if v.target_node_id is None:
            continue
        s_layer = graph.nodes.get(v.source_node_id, {}).get("layer", "unclassified")
        t_layer = graph.nodes.get(v.target_node_id, {}).get("layer", "unclassified")
        if s_layer != t_layer:
            violation_edges[(s_layer, t_layer)] += 1

    # Compute band heights
    band_heights = _compute_band_heights(layers_to_show, layer_files)

    # Calculate total canvas height
    bands_total_height = sum(band_heights.values()) + _BAND_GAP * max(len(layers_to_show) - 1, 0)
    canvas_height = _PADDING_TOP + bands_total_height + _LEGEND_HEIGHT + 40

    # Build SVG document
    svg = _create_svg_root(width, canvas_height)
    defs = _add_defs(svg)
    _add_arrow_markers(defs)

    # Background
    _add_rect(svg, 0, 0, width, canvas_height, fill=_COLOR_BG)

    # Title
    _add_text(
        svg, width / 2, 36,
        "Architecture Overview",
        font_size=_TITLE_FONT_SIZE,
        font_weight="bold",
        fill=_COLOR_TEXT_DARK,
        anchor="middle",
    )

    # Draw layer bands
    band_x = _PADDING_X
    band_width = width - 2 * _PADDING_X - _EDGE_AREA_WIDTH
    band_y_positions: dict[str, tuple[float, float]] = {}
    current_y = float(_PADDING_TOP)

    for layer in layers_to_show:
        band_h = band_heights[layer]
        color = _get_layer_color(config, layer)
        fill_with_alpha = color + "33"  # ~20% alpha

        _add_rect(
            svg, band_x, current_y, band_width, band_h,
            fill=fill_with_alpha,
            stroke=color,
            stroke_width=2,
            rx=_BAND_CORNER_RADIUS,
        )

        # Layer name (left-aligned)
        label_y = current_y + band_h / 2
        name_upper = layer.replace("_", " ").upper()
        _add_text(
            svg, band_x + 16, label_y,
            name_upper,
            font_size=_LAYER_LABEL_FONT_SIZE,
            font_weight="bold",
            fill=_COLOR_TEXT_DARK,
            anchor="start",
            dominant_baseline="central",
        )

        # File count (right-aligned)
        count = layer_files.get(layer, 0)
        file_label = f"{count} file{'s' if count != 1 else ''}"
        _add_text(
            svg, band_x + band_width - 16, label_y,
            file_label,
            font_size=_COUNT_FONT_SIZE,
            fill=_COLOR_TEXT_DARK,
            anchor="end",
            dominant_baseline="central",
        )

        band_y_positions[layer] = (current_y, band_h)
        current_y += band_h + _BAND_GAP

    # Draw inter-layer edge arrows
    edge_x_base = band_x + band_width + 20
    _draw_edges(
        svg, layers_to_show, band_y_positions,
        layer_edges, violation_edges,
        edge_x_base, width,
    )

    # Legend
    legend_y = current_y + 16
    _draw_legend(svg, _PADDING_X, legend_y)

    return _svg_to_string(svg)


def export_to_file(
    graph: nx.DiGraph,
    config: RubiconConfig,
    violations: list[Violation],
    output: Path,
) -> None:
    """Export the architecture diagram as SVG to a file.

    Args:
        graph: The architecture graph.
        config: Rubicon configuration.
        violations: Detected violations.
        output: Destination file path.
    """
    svg_content = export_svg(graph, config, violations)
    output.write_text(svg_content, encoding="utf-8")
    logger.info("SVG diagram written to %s", output)


# ---------------------------------------------------------------------------
# Internal helpers: layout
# ---------------------------------------------------------------------------

def _resolve_layer_order(
    config: RubiconConfig,
    layer_files: dict[str, int],
) -> list[str]:
    """Determine which layers to show and in what order."""
    layers = list(config.layer_order)
    for layer in sorted(layer_files.keys()):
        if layer not in layers and layer != "unclassified":
            layers.append(layer)
    if layer_files.get("unclassified", 0) > 0:
        layers.append("unclassified")
    return layers


def _compute_band_heights(
    layers: list[str],
    layer_files: dict[str, int],
) -> dict[str, float]:
    """Compute band heights proportional to file count."""
    if not layers:
        return {}

    max_count = max((layer_files.get(l, 0) for l in layers), default=1)
    max_count = max(max_count, 1)  # avoid division by zero

    heights: dict[str, float] = {}
    for layer in layers:
        count = layer_files.get(layer, 0)
        ratio = count / max_count
        height = _BAND_MIN_HEIGHT + ratio * (_BAND_MAX_HEIGHT - _BAND_MIN_HEIGHT)
        heights[layer] = height
    return heights


def _get_layer_color(config: RubiconConfig, layer: str) -> str:
    """Get the color for a layer from config, falling back to default."""
    layer_config = config.layers.get(layer)
    if layer_config and layer_config.color:
        return layer_config.color
    return _COLOR_DEFAULT_LAYER


# ---------------------------------------------------------------------------
# Internal helpers: SVG construction
# ---------------------------------------------------------------------------

def _create_svg_root(width: int, height: float) -> ET.Element:
    """Create the root SVG element."""
    svg = ET.Element("svg")
    svg.set("xmlns", "http://www.w3.org/2000/svg")
    svg.set("width", str(width))
    svg.set("height", str(int(math.ceil(height))))
    svg.set("viewBox", f"0 0 {width} {int(math.ceil(height))}")
    svg.set("font-family", _FONT_FAMILY)
    return svg


def _add_defs(svg: ET.Element) -> ET.Element:
    """Add a <defs> element to the SVG."""
    return ET.SubElement(svg, "defs")


def _add_arrow_markers(defs: ET.Element) -> None:
    """Add arrow marker definitions for clean and violation edges."""
    for marker_id, color in [("arrow-clean", _COLOR_CLEAN), ("arrow-violation", _COLOR_VIOLATION)]:
        marker = ET.SubElement(defs, "marker")
        marker.set("id", marker_id)
        marker.set("viewBox", "0 0 10 7")
        marker.set("refX", "10")
        marker.set("refY", "3.5")
        marker.set("markerWidth", "8")
        marker.set("markerHeight", "6")
        marker.set("orient", "auto-start-reverse")
        poly = ET.SubElement(marker, "polygon")
        poly.set("points", "0 0, 10 3.5, 0 7")
        poly.set("fill", color)


def _add_rect(
    parent: ET.Element,
    x: float, y: float, w: float, h: float,
    *,
    fill: str = "none",
    stroke: str = "none",
    stroke_width: float = 0,
    rx: float = 0,
) -> ET.Element:
    """Add a rectangle to the SVG."""
    rect = ET.SubElement(parent, "rect")
    rect.set("x", f"{x:.1f}")
    rect.set("y", f"{y:.1f}")
    rect.set("width", f"{w:.1f}")
    rect.set("height", f"{h:.1f}")
    rect.set("fill", fill)
    if stroke != "none":
        rect.set("stroke", stroke)
        rect.set("stroke-width", f"{stroke_width:.1f}")
    if rx > 0:
        rect.set("rx", f"{rx:.1f}")
    return rect


def _add_text(
    parent: ET.Element,
    x: float, y: float,
    text: str,
    *,
    font_size: int = 12,
    font_weight: str = "normal",
    fill: str = "#000000",
    anchor: str = "start",
    dominant_baseline: str = "auto",
) -> ET.Element:
    """Add a text element to the SVG."""
    elem = ET.SubElement(parent, "text")
    elem.set("x", f"{x:.1f}")
    elem.set("y", f"{y:.1f}")
    elem.set("font-size", str(font_size))
    if font_weight != "normal":
        elem.set("font-weight", font_weight)
    elem.set("fill", fill)
    elem.set("text-anchor", anchor)
    if dominant_baseline != "auto":
        elem.set("dominant-baseline", dominant_baseline)
    elem.text = text
    return elem


def _add_path(
    parent: ET.Element,
    d: str,
    *,
    stroke: str,
    stroke_width: float = 2,
    fill: str = "none",
    marker_end: str = "",
) -> ET.Element:
    """Add a path element to the SVG."""
    path = ET.SubElement(parent, "path")
    path.set("d", d)
    path.set("stroke", stroke)
    path.set("stroke-width", f"{stroke_width:.1f}")
    path.set("fill", fill)
    if marker_end:
        path.set("marker-end", f"url(#{marker_end})")
    return path


# ---------------------------------------------------------------------------
# Internal helpers: edge drawing
# ---------------------------------------------------------------------------

def _draw_edges(
    svg: ET.Element,
    layers: list[str],
    band_positions: dict[str, tuple[float, float]],
    layer_edges: dict[tuple[str, str], int],
    violation_edges: dict[tuple[str, str], int],
    edge_x_base: float,
    canvas_width: int,
) -> None:
    """Draw curved arrow edges between layer bands."""
    if not layers:
        return

    layer_index = {layer: i for i, layer in enumerate(layers)}

    # Merge all edge pairs
    all_pairs: set[tuple[str, str]] = set(layer_edges.keys()) | set(violation_edges.keys())

    # Sort by distance between layers for consistent visual ordering
    sorted_pairs = sorted(
        all_pairs,
        key=lambda pair: abs(layer_index.get(pair[0], 0) - layer_index.get(pair[1], 0)),
    )

    for idx, (s_layer, t_layer) in enumerate(sorted_pairs):
        if s_layer not in band_positions or t_layer not in band_positions:
            continue

        count = layer_edges.get((s_layer, t_layer), 0)
        v_count = violation_edges.get((s_layer, t_layer), 0)
        has_violations = v_count > 0

        color = _COLOR_VIOLATION if has_violations else _COLOR_CLEAN
        marker_id = "arrow-violation" if has_violations else "arrow-clean"

        # Compute Y positions: center of each band
        s_y, s_h = band_positions[s_layer]
        t_y, t_h = band_positions[t_layer]
        start_y = s_y + s_h / 2
        end_y = t_y + t_h / 2

        # Offset X for multiple edges to avoid overlap
        x_offset = edge_x_base + idx * 20
        x_offset = min(x_offset, canvas_width - 30)

        # Curved path using quadratic bezier
        mid_y = (start_y + end_y) / 2
        control_x = x_offset + 30

        d = (
            f"M {edge_x_base - 10:.1f},{start_y:.1f} "
            f"L {x_offset:.1f},{start_y:.1f} "
            f"Q {control_x:.1f},{mid_y:.1f} {x_offset:.1f},{end_y:.1f} "
            f"L {edge_x_base - 10:.1f},{end_y:.1f}"
        )
        _add_path(svg, d, stroke=color, stroke_width=1.5, marker_end=marker_id)

        # Edge label
        label_parts: list[str] = []
        if count > 0:
            label_parts.append(str(count))
        if v_count > 0:
            label_parts.append(f"{v_count} viol")
        label = " / ".join(label_parts) if label_parts else ""

        if label:
            label_x = control_x + 4
            label_y = mid_y
            _add_text(
                svg, label_x, label_y,
                label,
                font_size=_EDGE_LABEL_FONT_SIZE,
                fill=color,
                anchor="start",
                dominant_baseline="central",
            )


# ---------------------------------------------------------------------------
# Internal helpers: legend
# ---------------------------------------------------------------------------

def _draw_legend(svg: ET.Element, x: float, y: float) -> None:
    """Draw a legend at the bottom of the SVG."""
    # Clean connection
    _add_rect(svg, x, y, 16, 12, fill=_COLOR_CLEAN, rx=2)
    _add_text(
        svg, x + 22, y + 6,
        "Clean connection",
        font_size=_LEGEND_FONT_SIZE,
        fill=_COLOR_TEXT_DARK,
        dominant_baseline="central",
    )

    # Violation
    offset_x = x + 160
    _add_rect(svg, offset_x, y, 16, 12, fill=_COLOR_VIOLATION, rx=2)
    _add_text(
        svg, offset_x + 22, y + 6,
        "Violation",
        font_size=_LEGEND_FONT_SIZE,
        fill=_COLOR_TEXT_DARK,
        dominant_baseline="central",
    )


# ---------------------------------------------------------------------------
# SVG serialization
# ---------------------------------------------------------------------------

def _svg_to_string(svg: ET.Element) -> str:
    """Serialize the SVG element tree to a string with XML declaration."""
    ET.indent(svg, space="  ")
    raw = ET.tostring(svg, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + raw


