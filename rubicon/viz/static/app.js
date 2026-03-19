/* ===================================================================
   Rubicon — D3.js Architecture Visualization
   Single-file app, no framework, no build step.

   Level 1: Layer Block Diagram
   Level 2: File-Level View (force-directed)
   Level 3: Ratsnest View (radial layout)
   =================================================================== */

(function () {
    "use strict";

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------

    var state = {
        view: "layers",       // "layers" | "files" | "ratsnest"
        layerData: null,      // cached /api/layers response
        configData: null,     // cached /api/config response
        selectedLayer: null,  // for Level 2 single-layer drill-down
        sourceLayer: null,    // for Level 2 cross-layer drill-down
        targetLayer: null,    // for Level 2 cross-layer drill-down
        selectedFile: null,   // for Level 3 ratsnest
        navigating: false,    // guard against recursive hashchange events
        diffData: null,       // cached /api/diff response
        diffVisible: true     // whether diff overlay is shown
    };

    // ------------------------------------------------------------------
    // Highlight helpers
    // ------------------------------------------------------------------

    var DIM_OPACITY = 0.35;
    var NORMAL_OPACITY_ATTR = "data-normal-opacity";
    var HIGHLIGHT_MS = 120;

    /** Apply highlight: brighten connected elements, dim everything else.
     *  Does NOT touch pointer-events so hover transitions between elements
     *  remain smooth. */
    function applyHighlight(svg, connectedTest) {
        svg.selectAll(".layer-block").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 1 : DIM_OPACITY);
        });
        svg.selectAll(".layer-edge").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el)
                    ? (el.attr(NORMAL_OPACITY_ATTR) || 0.7) : DIM_OPACITY);
        });
        svg.selectAll(".edge-label, .edge-label-bg").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 1 : DIM_OPACITY);
        });
        svg.selectAll(".file-node").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 1 : DIM_OPACITY);
        });
        svg.selectAll(".file-edge").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 0.8 : DIM_OPACITY);
        });
        svg.selectAll(".cross-layer-connector").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 0.5 : DIM_OPACITY * 0.3);
        });
        svg.selectAll(".cross-layer-badge").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 1 : DIM_OPACITY);
        });
        svg.selectAll(".ratsnest-neighbor-node").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 1 : DIM_OPACITY);
        });
        svg.selectAll(".ratsnest-edge, .ratsnest-edge-label").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", connectedTest(el) ? 0.8 : DIM_OPACITY);
        });
    }

    /** Clear all highlights back to normal. */
    function clearHighlight(svg) {
        svg.selectAll(".layer-block, .file-node, .cross-layer-badge, .ratsnest-neighbor-node, .ratsnest-focus-node")
            .transition().duration(HIGHLIGHT_MS)
            .style("opacity", 1);
        svg.selectAll(".layer-edge").each(function () {
            var el = d3.select(this);
            el.transition().duration(HIGHLIGHT_MS)
                .style("opacity", el.attr(NORMAL_OPACITY_ATTR) || 0.7);
        });
        svg.selectAll(".file-edge").transition().duration(HIGHLIGHT_MS)
            .style("opacity", 0.6);
        svg.selectAll(".edge-label, .edge-label-bg").transition().duration(HIGHLIGHT_MS)
            .style("opacity", 1);
        svg.selectAll(".cross-layer-connector").transition().duration(HIGHLIGHT_MS)
            .style("opacity", 0.35);
        svg.selectAll(".ratsnest-edge, .ratsnest-edge-label").transition().duration(HIGHLIGHT_MS)
            .style("opacity", 0.6);
    }

    // ------------------------------------------------------------------
    // API helpers
    // ------------------------------------------------------------------

    function fetchJSON(url) {
        return fetch(url).then(function (res) {
            if (!res.ok) {
                throw new Error("HTTP " + res.status + " for " + url);
            }
            return res.json();
        });
    }

    // ------------------------------------------------------------------
    // Tooltip
    // ------------------------------------------------------------------

    var tooltipEl = document.getElementById("tooltip");

    function showTooltip(html, event) {
        tooltipEl.innerHTML = html;
        tooltipEl.style.display = "block";
        positionTooltip(event);
    }

    function positionTooltip(event) {
        var x = event.pageX + 14;
        var y = event.pageY + 14;
        var rect = tooltipEl.getBoundingClientRect();

        if (x + rect.width > window.innerWidth - 20) {
            x = event.pageX - rect.width - 14;
        }
        if (y + rect.height > window.innerHeight - 20) {
            y = event.pageY - rect.height - 14;
        }

        tooltipEl.style.left = x + "px";
        tooltipEl.style.top = y + "px";
    }

    function hideTooltip() {
        tooltipEl.style.display = "none";
    }

    // ------------------------------------------------------------------
    // Breadcrumb
    // ------------------------------------------------------------------

    function updateBreadcrumb(crumbs) {
        var nav = document.getElementById("breadcrumb");
        nav.innerHTML = "";

        crumbs.forEach(function (crumb, i) {
            if (i > 0) {
                var sep = document.createElement("span");
                sep.className = "separator";
                sep.textContent = "\u203A";
                nav.appendChild(sep);
            }

            var span = document.createElement("span");
            span.className = "crumb";
            span.textContent = crumb.label;

            if (i === crumbs.length - 1) {
                span.classList.add("active");
            } else {
                span.addEventListener("click", crumb.action);
            }

            nav.appendChild(span);
        });
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    function navigateToLayers() {
        if (activeSimulation) {
            activeSimulation.stop();
            activeSimulation = null;
        }
        state.navigating = true;
        state.view = "layers";
        state.selectedLayer = null;
        state.sourceLayer = null;
        state.targetLayer = null;
        state.selectedFile = null;
        window.location.hash = "";
        renderLayerDiagram();
        state.navigating = false;
    }

    function navigateToFiles(layer, sourceLayer, targetLayer) {
        state.navigating = true;
        state.view = "files";
        state.selectedLayer = layer || null;
        state.sourceLayer = sourceLayer || null;
        state.targetLayer = targetLayer || null;
        state.selectedFile = null;

        if (layer) {
            window.location.hash = "#/layer/" + encodeURIComponent(layer);
        } else if (sourceLayer && targetLayer) {
            window.location.hash = "#/edge/" + encodeURIComponent(sourceLayer) +
                "/" + encodeURIComponent(targetLayer);
        }
        renderFileView();
        state.navigating = false;
    }

    function navigateToRatsnest(fileId) {
        state.navigating = true;
        state.view = "ratsnest";
        state.selectedFile = fileId;
        window.location.hash = "#/file/" + encodeURIComponent(fileId);
        renderRatsnestView();
        state.navigating = false;
    }

    // ------------------------------------------------------------------
    // Hash-based routing
    // ------------------------------------------------------------------

    function handleHashChange() {
        // Skip if we triggered this change ourselves
        if (state.navigating) return;

        var hash = window.location.hash;

        if (!hash || hash === "#" || hash === "#/") {
            navigateToLayers();
            return;
        }

        var layerMatch = hash.match(/^#\/layer\/(.+)$/);
        if (layerMatch) {
            navigateToFiles(decodeURIComponent(layerMatch[1]), null, null);
            return;
        }

        var edgeMatch = hash.match(/^#\/edge\/([^/]+)\/(.+)$/);
        if (edgeMatch) {
            navigateToFiles(
                null,
                decodeURIComponent(edgeMatch[1]),
                decodeURIComponent(edgeMatch[2])
            );
            return;
        }

        var fileMatch = hash.match(/^#\/file\/(.+)$/);
        if (fileMatch) {
            navigateToRatsnest(decodeURIComponent(fileMatch[1]));
            return;
        }

        navigateToLayers();
    }

    // ------------------------------------------------------------------
    // Level 1: Layer Block Diagram
    // ------------------------------------------------------------------

    function renderLayerDiagram() {
        updateBreadcrumb([{ label: "Layers", action: navigateToLayers }]);

        var svg = d3.select("#layer-diagram");
        svg.selectAll("*").remove();

        if (!state.layerData || !state.layerData.layers ||
            state.layerData.layers.length === 0) {
            renderEmptyState(svg, "No layers found. Check your .rubicon config.");
            return;
        }

        var data = state.layerData;
        var config = state.configData;
        var layers = data.layers;
        var edges = data.edges;

        var container = document.getElementById("viz-container");
        var containerW = container.clientWidth;
        var containerH = container.clientHeight;

        // Use a temporary viewBox so elements can be measured after drawing
        svg.attr("viewBox", "0 0 " + containerW + " " + containerH);

        // Define arrow markers
        var defs = svg.append("defs");
        defineArrowMarkers(defs);

        // Layout strata based on container height; width will be fitted after
        var layout = computeLayout(layers, containerW, containerH);

        // Draw edges first (behind blocks)
        var edgeGroup = svg.append("g").attr("class", "edges");
        drawEdges(edgeGroup, edges, layout, layers);

        // Draw layer blocks
        var blockGroup = svg.append("g").attr("class", "blocks");
        drawLayerBlocks(blockGroup, layers, layout, data);

        // Fit viewBox to actual rendered content with padding
        var fitPad = 24;
        var bbox = svg.node().getBBox();
        var vbX = bbox.x - fitPad;
        var vbY = bbox.y - fitPad;
        var vbW = bbox.width + fitPad * 2;
        var vbH = bbox.height + fitPad * 2;
        svg.attr("viewBox", vbX + " " + vbY + " " + vbW + " " + vbH);
    }

    function renderEmptyState(svg, message) {
        var container = document.getElementById("viz-container");
        var width = container.clientWidth;
        var height = container.clientHeight;

        svg.attr("viewBox", "0 0 " + width + " " + height);

        var g = svg.append("g")
            .attr("transform", "translate(" + width / 2 + "," + height / 2 + ")");

        g.append("text")
            .attr("text-anchor", "middle")
            .attr("y", -20)
            .attr("fill", "#8888aa")
            .attr("font-size", "48px")
            .attr("opacity", 0.4)
            .text("\u25A1");

        g.append("text")
            .attr("text-anchor", "middle")
            .attr("y", 25)
            .attr("fill", "#8888aa")
            .attr("font-size", "16px")
            .text(message);
    }

    // ------------------------------------------------------------------
    // Layout computation
    // ------------------------------------------------------------------

    function computeLayout(layers, width, height) {
        var n = layers.length;
        if (n === 0) return {};

        // Geological strata layout: horizontal bands stacked top to bottom.
        // Top layer = closest to user (presentation), bottom = closest to data source.
        // Right side reserved for edge corridors.
        var paddingX = 40;
        var paddingY = 30;
        var gap = 6;  // thin gap between strata
        var edgeCorridor = 200; // space on right for curved edges

        var availWidth = width - paddingX - edgeCorridor;
        var availHeight = height - 2 * paddingY - (n - 1) * gap;

        // Height proportional to file count
        var totalFiles = 0;
        layers.forEach(function (l) { totalFiles += l.file_count; });
        if (totalFiles === 0) totalFiles = n;

        var minH = 48;
        var positions = {};
        var y = paddingY;

        layers.forEach(function (layer) {
            var ratio = layer.file_count / totalFiles;
            var h = Math.max(minH, availHeight * ratio);
            var w = availWidth;
            var x = paddingX;

            positions[layer.name] = {
                x: x,
                y: y,
                w: w,
                h: h,
                cx: x + w / 2,
                cy: y + h / 2
            };

            y += h + gap;
        });

        return positions;
    }

    // ------------------------------------------------------------------
    // Arrow marker definitions
    // ------------------------------------------------------------------

    function defineArrowMarkers(defs) {
        var types = [
            { name: "clean", color: "#3ddc84" },
            { name: "warning", color: "#ffc107" },
            { name: "error", color: "#f44336" }
        ];

        types.forEach(function (t) {
            defs.append("marker")
                .attr("id", "arrow-" + t.name)
                .attr("viewBox", "0 0 10 10")
                .attr("refX", 10)
                .attr("refY", 5)
                .attr("markerWidth", 8)
                .attr("markerHeight", 8)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,0 L10,5 L0,10 Z")
                .attr("fill", t.color);
        });
    }

    // ------------------------------------------------------------------
    // Draw layer blocks
    // ------------------------------------------------------------------

    function drawLayerBlocks(group, layers, layout, data) {
        // Compute layer diff summary once for all layers
        var layerDiff = null;
        if (state.diffData && state.diffData.enabled && state.diffVisible) {
            layerDiff = buildLayerDiffSummary(state.diffData);
        }

        layers.forEach(function (layer) {
            var pos = layout[layer.name];
            if (!pos) return;

            var g = group.append("g")
                .attr("class", "layer-block stratum")
                .attr("data-layer", layer.name)
                .attr("transform", "translate(" + pos.x + "," + pos.y + ")")
                .on("click", function () {
                    navigateToFiles(layer.name, null, null);
                })
                .on("mouseover", function () {
                    // Highlight this layer and its connections
                    var svg = d3.select("#layer-diagram");
                    var layerName = layer.name;
                    var connected = {};
                    connected[layerName] = true;
                    data.edges.forEach(function (e) {
                        if (e.source === layerName || e.target === layerName) {
                            connected[e.source] = true;
                            connected[e.target] = true;
                        }
                    });
                    applyHighlight(svg, function (el) {
                        var dl = el.attr("data-layer");
                        var ds = el.attr("data-source");
                        var dt = el.attr("data-target");
                        if (dl) return !!connected[dl];
                        if (ds && dt) return (ds === layerName || dt === layerName);
                        return false;
                    });
                })
                .on("mouseout", function () {
                    clearHighlight(d3.select("#layer-diagram"));
                });

            // Stratum background — full-width band
            g.append("rect")
                .attr("width", pos.w)
                .attr("height", pos.h)
                .attr("fill", layer.color)
                .attr("fill-opacity", 0.12)
                .attr("stroke", "none");

            // Left accent bar
            g.append("rect")
                .attr("width", 4)
                .attr("height", pos.h)
                .attr("fill", layer.color)
                .attr("fill-opacity", 0.8);

            // Layer name — left-aligned
            g.append("text")
                .attr("class", "layer-name stratum-name")
                .attr("x", 20)
                .attr("y", pos.h / 2 + 1)
                .attr("dominant-baseline", "middle")
                .text(layer.name);

            // File count — right of name
            g.append("text")
                .attr("class", "layer-count")
                .attr("x", 20 + layer.name.length * 10 + 16)
                .attr("y", pos.h / 2 + 1)
                .attr("dominant-baseline", "middle")
                .text(layer.file_count + (layer.file_count === 1 ? " file" : " files"));

            // Violation badge — right side
            var layerViolations = countLayerViolations(layer.name, data.edges);
            if (layerViolations > 0) {
                var badgeX = pos.w - 24;
                var badgeY = pos.h / 2;
                var badgeW = Math.max(20, String(layerViolations).length * 10 + 10);

                g.append("rect")
                    .attr("class", "violation-badge-bg")
                    .attr("x", badgeX - badgeW / 2)
                    .attr("y", badgeY - 9)
                    .attr("width", badgeW)
                    .attr("height", 18);

                g.append("text")
                    .attr("class", "violation-badge")
                    .attr("x", badgeX)
                    .attr("y", badgeY + 4)
                    .text(layerViolations);
            }

            // Diff overlay: +/- file count badges
            if (layerDiff) {
                var added = layerDiff.addedFiles[layer.name] || 0;
                var removed = layerDiff.removedFiles[layer.name] || 0;
                var diffBadgeX = 20;
                var diffBadgeY = pos.h / 2 + 16;

                if (added > 0) {
                    var addedText = "+" + added + " file" + (added !== 1 ? "s" : "");
                    g.append("text")
                        .attr("class", "diff-file-badge added")
                        .attr("x", diffBadgeX)
                        .attr("y", diffBadgeY)
                        .text(addedText);
                    diffBadgeX += addedText.length * 7 + 12;
                }
                if (removed > 0) {
                    g.append("text")
                        .attr("class", "diff-file-badge removed")
                        .attr("x", diffBadgeX)
                        .attr("y", diffBadgeY)
                        .text("-" + removed + " file" + (removed !== 1 ? "s" : ""));
                }

                // New/resolved violation badges on layer block
                var newV = layerDiff.newLayerViolations[layer.name] || 0;
                var resolvedV = layerDiff.resolvedLayerViolations[layer.name] || 0;
                var violBadgeX = 20;
                var violBadgeY = diffBadgeY + 16;
                if (newV > 0) {
                    var newText = newV + " NEW in " + layer.name;
                    g.append("text")
                        .attr("class", "diff-tag new diff-viol-badge")
                        .attr("x", violBadgeX)
                        .attr("y", violBadgeY)
                        .attr("font-size", "13px")
                        .text(newText);
                    violBadgeX += newText.length * 7 + 12;
                }
                if (resolvedV > 0) {
                    g.append("text")
                        .attr("class", "diff-tag resolved")
                        .attr("x", violBadgeX)
                        .attr("y", violBadgeY)
                        .attr("font-size", "13px")
                        .text("\u2713 " + resolvedV + " RESOLVED in " + layer.name);
                }
            }
        });
    }

    function countLayerViolations(layerName, edges) {
        var count = 0;
        edges.forEach(function (e) {
            if (e.source === layerName || e.target === layerName) {
                count += e.violations || 0;
            }
        });
        return count;
    }

    // ------------------------------------------------------------------
    // Draw edges between layers
    // ------------------------------------------------------------------

    function drawEdges(group, edges, layout, layers) {
        // Reset edge slot counter for corridor spacing
        edgeSlotIndex = 0;
        edgeSlotTotal = edges.length;

        // Compute layer diff summary once for all edges
        var layerDiff = null;
        if (state.diffData && state.diffData.enabled && state.diffVisible) {
            layerDiff = buildLayerDiffSummary(state.diffData);
        }

        edges.forEach(function (edge) {
            var sourcePos = layout[edge.source];
            var targetPos = layout[edge.target];
            if (!sourcePos || !targetPos) return;

            var edgeClass = "clean";
            if (edge.violations > 0) {
                edgeClass = "error";
            }

            var thickness = Math.max(1.5, Math.min(8, Math.log2(edge.count + 1) * 2));
            var opacity = Math.max(0.4, Math.min(0.9, 0.4 + edge.count * 0.05));

            // Compute path between block edges
            var pathData = computeEdgePath(sourcePos, targetPos);

            var path = group.append("path")
                .attr("class", "layer-edge " + edgeClass)
                .attr("data-source", edge.source)
                .attr("data-target", edge.target)
                .attr("d", pathData.d)
                .attr("stroke-width", thickness)
                .attr("opacity", opacity)
                .attr(NORMAL_OPACITY_ATTR, opacity)
                .attr("marker-end", "url(#arrow-" + edgeClass + ")")
                .on("click", function () {
                    navigateToFiles(null, edge.source, edge.target);
                })
                .on("mouseover", function () {
                    // Highlight this edge and its endpoint layers
                    var svg = d3.select("#layer-diagram");
                    var connected = {};
                    connected[edge.source] = true;
                    connected[edge.target] = true;
                    applyHighlight(svg, function (el) {
                        var dl = el.attr("data-layer");
                        var ds = el.attr("data-source");
                        var dt = el.attr("data-target");
                        if (dl) return !!connected[dl];
                        if (ds && dt) return ds === edge.source && dt === edge.target;
                        return false;
                    });
                })
                .on("mouseout", function () {
                    clearHighlight(d3.select("#layer-diagram"));
                });

            // Edge label (connection count)
            var midX = pathData.midX;
            var midY = pathData.midY;

            var label = String(edge.count);
            var labelW = label.length * 8 + 12;

            group.append("rect")
                .attr("class", "edge-label-bg")
                .attr("x", midX - labelW / 2)
                .attr("y", midY - 9)
                .attr("width", labelW)
                .attr("height", 18);

            group.append("text")
                .attr("class", "edge-label")
                .attr("x", midX)
                .attr("y", midY + 4)
                .text(label);

            // Diff badges next to edge label
            if (layerDiff) {
                var edgeKey = edge.source + ":" + edge.target;
                var diffAdded = layerDiff.addedEdges[edgeKey] || 0;
                var diffRemoved = layerDiff.removedEdges[edgeKey] || 0;
                var diffNewViol = layerDiff.newViolations[edgeKey] || 0;
                var diffResolved = layerDiff.resolvedViolations[edgeKey] || 0;
                var diffY = midY + 18;

                if (diffAdded > 0) {
                    group.append("text")
                        .attr("class", "diff-file-badge added")
                        .attr("x", midX)
                        .attr("y", diffY)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "12px")
                        .text("+" + diffAdded + " " + edge.source + "\u2192" + edge.target);
                    diffY += 16;
                }
                if (diffRemoved > 0) {
                    group.append("text")
                        .attr("class", "diff-file-badge removed")
                        .attr("x", midX)
                        .attr("y", diffY)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "12px")
                        .text("-" + diffRemoved + " " + edge.source + "\u2192" + edge.target);
                    diffY += 16;
                }
                if (diffNewViol > 0) {
                    group.append("text")
                        .attr("class", "diff-tag new diff-viol-badge")
                        .attr("x", midX)
                        .attr("y", diffY)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "12px")
                        .text(diffNewViol + " NEW " + edge.source + "\u2192" + edge.target);
                    diffY += 16;
                }
                if (diffResolved > 0) {
                    group.append("text")
                        .attr("class", "diff-tag resolved")
                        .attr("x", midX)
                        .attr("y", diffY)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "12px")
                        .text("\u2713 " + diffResolved + " RESOLVED " + edge.source + "\u2192" + edge.target);
                }
            }
        });
    }

    /** Track how many edges share the same right-side corridor to space them out. */
    var edgeSlotIndex = 0;
    var edgeSlotTotal = 0;

    function computeEdgePath(sourcePos, targetPos) {
        // For geological strata, edges exit the right side and curve through
        // a corridor on the right, connecting vertically between layers.
        var rightMargin = 60;
        var slotWidth = 30;

        // Source exits from right edge at vertical center
        var srcX = sourcePos.x + sourcePos.w;
        var srcY = sourcePos.cy;
        var tgtX = targetPos.x + targetPos.w;
        var tgtY = targetPos.cy;

        // Spread multiple edges so they don't overlap
        var slot = edgeSlotIndex;
        var corridorX = Math.max(srcX, tgtX) + rightMargin + slot * slotWidth;
        edgeSlotIndex++;

        var d = "M" + srcX + "," + srcY +
            " C" + corridorX + "," + srcY +
            " " + corridorX + "," + tgtY +
            " " + tgtX + "," + tgtY;

        var midX = corridorX;
        var midY = (srcY + tgtY) / 2;

        return { d: d, midX: midX, midY: midY };
    }

    function findEdgePoint(rect, toX, toY) {
        // Find the point on the rectangle border closest to (toX, toY)
        var cx = rect.cx;
        var cy = rect.cy;
        var hw = rect.w / 2;
        var hh = rect.h / 2;

        var dx = toX - cx;
        var dy = toY - cy;

        if (dx === 0 && dy === 0) {
            return { x: cx, y: cy - hh };
        }

        var absDx = Math.abs(dx);
        var absDy = Math.abs(dy);

        var scale;
        if (absDx / hw > absDy / hh) {
            scale = hw / absDx;
        } else {
            scale = hh / absDy;
        }

        return {
            x: cx + dx * scale,
            y: cy + dy * scale
        };
    }

    // ------------------------------------------------------------------
    // Relationship type color mapping (shared by Level 2 and Level 3)
    // ------------------------------------------------------------------

    var REL_COLORS = {
        "import":      "#4A90D9",  // blue
        "inheritance": "#E8A838",  // orange
        "ownership":   "#9B59B6",  // purple
        "function_call": "#1ABC9C" // teal
    };

    function relColor(type) {
        return REL_COLORS[type] || "#888888";
    }

    /** Return the dominant relationship type for an edge. */
    function dominantRelType(rels) {
        if (!rels || rels.length === 0) return "import";
        var counts = {};
        rels.forEach(function (r) {
            counts[r.type] = (counts[r.type] || 0) + 1;
        });
        var best = rels[0].type;
        var bestCount = 0;
        Object.keys(counts).forEach(function (t) {
            if (counts[t] > bestCount) {
                bestCount = counts[t];
                best = t;
            }
        });
        return best;
    }

    /** Check if an edge has a violation associated with it. */
    function edgeHasViolation(edge, violations) {
        for (var i = 0; i < violations.length; i++) {
            var v = violations[i];
            if (v.source_node_id === edge.source && v.target_node_id === edge.target) {
                return v;
            }
            if (v.source_node_id === edge.target && v.target_node_id === edge.source) {
                return v;
            }
        }
        return null;
    }

    /** Extract filename from full path. */
    function fileName(filePath) {
        if (!filePath) return "";
        var parts = String(filePath).split("/");
        return parts[parts.length - 1];
    }

    // ------------------------------------------------------------------
    // Level 2: File-Level View (force-directed)
    // ------------------------------------------------------------------

    /** Active force simulation reference so we can stop it on navigation. */
    var activeSimulation = null;

    /** Track the current render generation to discard stale async responses. */
    var fileViewGeneration = 0;

    function renderFileView() {
        // Stop any running simulation from a previous view
        if (activeSimulation) {
            activeSimulation.stop();
            activeSimulation = null;
        }

        // Increment generation so in-flight fetches from prior renders are discarded
        var thisGeneration = ++fileViewGeneration;

        // Build breadcrumb label
        var label;
        if (state.selectedLayer) {
            label = state.selectedLayer;
        } else {
            label = state.sourceLayer + " \u2192 " + state.targetLayer;
        }

        updateBreadcrumb([
            { label: "Layers", action: navigateToLayers },
            { label: label, action: function () {} }
        ]);

        // Build API URL
        var url;
        if (state.selectedLayer) {
            url = "/api/files?layer=" + encodeURIComponent(state.selectedLayer);
        } else {
            url = "/api/files?source_layer=" + encodeURIComponent(state.sourceLayer) +
                "&target_layer=" + encodeURIComponent(state.targetLayer);
        }

        var svg = d3.select("#layer-diagram");
        svg.selectAll("*").remove();

        fetchJSON(url).then(function (data) {
            // Discard if a newer render has started
            if (thisGeneration !== fileViewGeneration) return;

            if (!data.nodes || data.nodes.length === 0) {
                renderEmptyState(svg, "No files found in this view.");
                return;
            }
            renderFileForceLayout(svg, data);
        }).catch(function (err) {
            if (thisGeneration !== fileViewGeneration) return;
            console.error("Failed to load file data:", err);
            renderEmptyState(svg, "Failed to load file data.");
        });
    }

    function renderFileForceLayout(svg, data) {
        var container = document.getElementById("viz-container");
        var width = container.clientWidth;
        var height = container.clientHeight;

        // Classify cross-layer connections by position before computing margins
        var crossConnections = data.cross_layer_connections || [];
        var layerOrder = (state.configData && state.configData.layer_order) || [];
        var currentIdx = layerOrder.indexOf(state.selectedLayer);
        var hasSideBadges = crossConnections.some(function (cc) {
            var extIdx = layerOrder.indexOf(cc.layer);
            return !(currentIdx >= 0 && extIdx >= 0 &&
                (extIdx === currentIdx - 1 || extIdx === currentIdx + 1));
        });
        var badgeMargin = hasSideBadges ? 180 : 0;
        var innerWidth = width - badgeMargin;

        svg.attr("viewBox", "0 0 " + width + " " + height);

        // Defs for arrow markers (per relationship type + violation)
        var defs = svg.append("defs");
        defineFileArrowMarkers(defs);

        // Arrow markers for cross-layer connectors
        if (crossConnections.length > 0) {
            crossConnections.forEach(function (cc) {
                var safeName = cc.layer.replace(/[^a-zA-Z0-9]/g, "_");
                defs.append("marker")
                    .attr("id", "xarrow-out-" + safeName)
                    .attr("viewBox", "0 0 10 10")
                    .attr("refX", 10)
                    .attr("refY", 5)
                    .attr("markerWidth", 6)
                    .attr("markerHeight", 6)
                    .attr("orient", "auto")
                    .append("path")
                    .attr("d", "M0,0 L10,5 L0,10 Z")
                    .attr("fill", cc.color);
                defs.append("marker")
                    .attr("id", "xarrow-in-" + safeName)
                    .attr("viewBox", "0 0 10 10")
                    .attr("refX", 0)
                    .attr("refY", 5)
                    .attr("markerWidth", 6)
                    .attr("markerHeight", 6)
                    .attr("orient", "auto")
                    .append("path")
                    .attr("d", "M10,0 L0,5 L10,10 Z")
                    .attr("fill", cc.color);
            });
        }

        // Build node and link data for D3 force simulation
        var nodeMap = {};
        var nodes = data.nodes.map(function (n) {
            var obj = {
                id: n.id,
                file_path: n.file_path,
                language: n.language,
                layer: n.layer,
                symbols: n.symbols,
                label: fileName(n.file_path)
            };
            nodeMap[n.id] = obj;
            return obj;
        });

        var links = [];
        data.edges.forEach(function (e) {
            if (nodeMap[e.source] && nodeMap[e.target]) {
                var violation = edgeHasViolation(e, data.violations);
                links.push({
                    source: e.source,
                    target: e.target,
                    relationships: e.relationships,
                    relType: dominantRelType(e.relationships),
                    violation: violation
                });
            }
        });

        // Diff overlay: build lookup sets
        var diffAddedNodes = {};
        var diffAddedEdges = {};

        if (state.diffData && state.diffData.enabled && state.diffVisible) {
            (state.diffData.added_nodes || []).forEach(function (nid) {
                diffAddedNodes[nid] = true;
            });
            (state.diffData.added_edges || []).forEach(function (e) {
                diffAddedEdges[e.source + ":" + e.target] = true;
            });
        }

        // Create groups for edges and nodes
        var edgeGroup = svg.append("g").attr("class", "file-edges");
        var nodeGroup = svg.append("g").attr("class", "file-nodes");

        // Draw edges (lines with arrows)
        var linkSelection = edgeGroup.selectAll("line")
            .data(links)
            .enter()
            .append("line")
            .attr("class", function (d) {
                var cls = "file-edge";
                if (d.violation) cls += " violation";
                var key = (d.source.id || d.source) + ":" + (d.target.id || d.target);
                if (diffAddedEdges[key]) cls += " diff-added";
                return cls;
            })
            .attr("data-source", function (d) { return d.source.id || d.source; })
            .attr("data-target", function (d) { return d.target.id || d.target; })
            .attr("stroke", function (d) {
                return d.violation ? "#f44336" : relColor(d.relType);
            })
            .attr("stroke-width", function (d) {
                return d.violation ? 3 : 1.5;
            })
            .attr("marker-end", function (d) {
                return d.violation ? "url(#file-arrow-violation)" :
                    "url(#file-arrow-" + d.relType + ")";
            })
;

        // Draw nodes (circles with labels)
        var nodeRadius = 20;
        var nodeSelection = nodeGroup.selectAll("g")
            .data(nodes)
            .enter()
            .append("g")
            .attr("class", function (d) {
                var cls = "file-node";
                if (diffAddedNodes[d.id]) cls += " diff-added";
                return cls;
            })
            .attr("data-file-id", function (d) { return d.id; })
            .on("click", function (event, d) {
                // Store the layer for breadcrumb navigation back from Level 3
                state.selectedLayer = state.selectedLayer || d.layer;
                navigateToRatsnest(d.id);
            })
            .on("mouseover", function (event, d) {
                // Highlight this file and its connections
                var svg = d3.select("#layer-diagram");
                var connected = {};
                connected[d.id] = true;
                var connectedBadgeLayers = {};
                links.forEach(function (l) {
                    var sid = l.source.id || l.source;
                    var tid = l.target.id || l.target;
                    if (sid === d.id) { connected[tid] = true; }
                    if (tid === d.id) { connected[sid] = true; }
                });
                connectors.forEach(function (c) {
                    if (c.fileId === d.id) {
                        connectedBadgeLayers[c.badge.layer] = true;
                    }
                });
                applyHighlight(svg, function (el) {
                    var fid = el.attr("data-file-id");
                    var ds = el.attr("data-source");
                    var dt = el.attr("data-target");
                    var dl = el.attr("data-layer");
                    var dcf = el.attr("data-conn-file");
                    if (fid) return !!connected[fid];
                    if (ds && dt) return ds === d.id || dt === d.id;
                    if (dl) return !!connectedBadgeLayers[dl];
                    if (dcf) return dcf === d.id;
                    return false;
                });
            })
            .on("mouseout", function () {
                clearHighlight(d3.select("#layer-diagram"));
            })
            .call(d3.drag()
                .on("start", function (event, d) {
                    if (window._rubiconDrag) window._rubiconDrag.active = true;
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on("drag", function (event, d) {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on("end", function (event, d) {
                    if (window._rubiconDrag) window._rubiconDrag.active = false;
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                })
            );

        // Node circle — color by layer
        nodeSelection.append("circle")
            .attr("r", nodeRadius)
            .attr("fill", function (d) {
                return layerColor(d.layer);
            })
            .attr("fill-opacity", 0.2)
            .attr("stroke", function (d) {
                return layerColor(d.layer);
            })
            .attr("stroke-width", 2);

        // Node label (filename)
        nodeSelection.append("text")
            .attr("class", "file-node-label")
            .attr("dy", nodeRadius + 16)
            .text(function (d) { return d.label; });

        // Layer badge (small colored pill above node)
        nodeSelection.append("rect")
            .attr("class", "file-layer-badge-bg")
            .attr("x", function (d) { return -(d.layer.length * 3.5 + 6); })
            .attr("y", -(nodeRadius + 18))
            .attr("width", function (d) { return d.layer.length * 7 + 12; })
            .attr("height", 14)
            .attr("fill", function (d) { return layerColor(d.layer); })
            .attr("fill-opacity", 0.3)
            .attr("rx", 3)
            .attr("ry", 3);

        nodeSelection.append("text")
            .attr("class", "file-layer-badge-text")
            .attr("y", -(nodeRadius + 8))
            .text(function (d) { return d.layer; });

        // --- Cross-layer connection badges and connectors ---
        var connectorGroup = svg.append("g").attr("class", "cross-layer-connectors");
        var badgeGroup = svg.append("g").attr("class", "cross-layer-badges");

        var badges = [];
        var connectors = [];
        var topMargin = 0;
        var bottomMargin = 0;
        var badgeH = 28;

        if (crossConnections.length > 0) {

            // Classify badges as "above", "below", or "side" using layer_order
            var aboveBadges = [];
            var belowBadges = [];
            var sideBadges = [];

            crossConnections.forEach(function (cc) {
                var extIdx = layerOrder.indexOf(cc.layer);
                var badge = {
                    layer: cc.layer,
                    color: cc.color,
                    x: 0,
                    y: 0,
                    position: "side",
                    outbound_files: cc.outbound_files || [],
                    inbound_files: cc.inbound_files || [],
                    safeName: cc.layer.replace(/[^a-zA-Z0-9]/g, "_")
                };

                if (currentIdx >= 0 && extIdx >= 0 && extIdx === currentIdx - 1) {
                    badge.position = "above";
                    aboveBadges.push(badge);
                } else if (currentIdx >= 0 && extIdx >= 0 && extIdx === currentIdx + 1) {
                    badge.position = "below";
                    belowBadges.push(badge);
                } else {
                    badge.position = "side";
                    sideBadges.push(badge);
                }
            });

            // Position: above badges centered at top
            topMargin = aboveBadges.length > 0 ? 50 : 0;
            bottomMargin = belowBadges.length > 0 ? 50 : 0;

            aboveBadges.forEach(function (b, i) {
                b.x = innerWidth / 2 + (i - (aboveBadges.length - 1) / 2) * 160;
                b.y = 24;
            });

            // Position: below badges centered at bottom
            belowBadges.forEach(function (b, i) {
                b.x = innerWidth / 2 + (i - (belowBadges.length - 1) / 2) * 160;
                b.y = height - 24;
            });

            // Position: side badges along right edge
            var sideX = innerWidth + badgeMargin / 2;
            var sideSpacing = Math.min(60, (height - 80) / (sideBadges.length + 1));
            var sideStartY = height / 2 - ((sideBadges.length - 1) * sideSpacing) / 2;
            sideBadges.forEach(function (b, i) {
                b.x = sideX;
                b.y = sideStartY + i * sideSpacing;
            });

            badges = aboveBadges.concat(belowBadges).concat(sideBadges);

            // Compute total unique connected files per badge
            badges.forEach(function (badge) {
                var seen = {};
                badge.outbound_files.concat(badge.inbound_files).forEach(function (fid) {
                    seen[fid] = true;
                });
                badge.totalCount = Object.keys(seen).length;
            });

            function badgeLabel(d) {
                return d.layer + " (" + (d.totalCount || 0) + ")";
            }

            // Build connector data: one connector per file→badge link
            badges.forEach(function (badge) {
                badge.outbound_files.forEach(function (fileId) {
                    connectors.push({ fileId: fileId, badge: badge, direction: "outbound" });
                });
                badge.inbound_files.forEach(function (fileId) {
                    connectors.push({ fileId: fileId, badge: badge, direction: "inbound" });
                });
            });

            // Render badge backgrounds and labels
            var badgeSelection = badgeGroup.selectAll("g")
                .data(badges)
                .enter()
                .append("g")
                .attr("class", "cross-layer-badge")
                .attr("data-layer", function (d) { return d.layer; })
                .style("cursor", "pointer")
                .attr("transform", function (d) {
                    return "translate(" + d.x + "," + d.y + ")";
                })
                .on("click", function (event, d) {
                    navigateToFiles(d.layer, null, null);
                })
                .on("mouseover", function (event, d) {
                    // Highlight badge and all connected files + connectors
                    var svg = d3.select("#layer-diagram");
                    var connectedFiles = {};
                    d.outbound_files.forEach(function (fid) { connectedFiles[fid] = true; });
                    d.inbound_files.forEach(function (fid) { connectedFiles[fid] = true; });
                    applyHighlight(svg, function (el) {
                        var fid = el.attr("data-file-id");
                        var dl = el.attr("data-layer");
                        var dcf = el.attr("data-conn-file");
                        var ds = el.attr("data-source");
                        var dt = el.attr("data-target");
                        if (dl) return dl === d.layer;
                        if (fid) return !!connectedFiles[fid];
                        if (dcf) return !!connectedFiles[dcf];
                        if (ds && dt) return !!connectedFiles[ds] && !!connectedFiles[dt];
                        return false;
                    });
                })
                .on("mouseout", function () {
                    clearHighlight(d3.select("#layer-diagram"));
                });

            badgeSelection.append("rect")
                .attr("x", function (d) { return -(badgeLabel(d).length * 3.5 + 12); })
                .attr("y", -badgeH / 2)
                .attr("width", function (d) { return badgeLabel(d).length * 7 + 24; })
                .attr("height", badgeH)
                .attr("rx", 14)
                .attr("ry", 14)
                .attr("fill", function (d) { return d.color; })
                .attr("fill-opacity", 0.25)
                .attr("stroke", function (d) { return d.color; })
                .attr("stroke-width", 1.5);

            badgeSelection.append("text")
                .attr("text-anchor", "middle")
                .attr("dy", "0.35em")
                .attr("fill", function (d) { return d.color; })
                .attr("font-size", "12px")
                .attr("font-weight", "600")
                .text(badgeLabel);

            // Render connector paths (will be updated in tick)
            var connectorSelection = connectorGroup.selectAll("path")
                .data(connectors)
                .enter()
                .append("path")
                .attr("class", "cross-layer-connector")
                .attr("data-conn-file", function (d) { return d.fileId; })
                .attr("fill", "none")
                .attr("stroke", function (d) { return d.badge.color; })
                .attr("stroke-width", 1)
                .attr("stroke-opacity", 0.35)
                .attr("stroke-dasharray", "4,3")
                .attr("marker-end", function (d) {
                    if (d.direction === "outbound") {
                        return "url(#xarrow-out-" + d.badge.safeName + ")";
                    }
                    return "";
                })
                .attr("marker-start", function (d) {
                    if (d.direction === "inbound") {
                        return "url(#xarrow-in-" + d.badge.safeName + ")";
                    }
                    return "";
                });
        }

        // Force simulation — center nodes within the area between badges
        var innerTop = topMargin + nodeRadius + 10;
        var innerBottom = height - bottomMargin - nodeRadius - 10;
        var centerY = (innerTop + innerBottom) / 2;

        var simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(function (d) { return d.id; }).distance(120))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(innerWidth / 2, centerY))
            .force("collision", d3.forceCollide(nodeRadius + 10))
            .force("x", d3.forceX(innerWidth / 2).strength(0.05))
            .force("y", d3.forceY(centerY).strength(0.05))
            .on("tick", tick);

        activeSimulation = simulation;

        function tick() {
            // Keep nodes within bounds (respecting all badge margins)
            nodes.forEach(function (d) {
                d.x = Math.max(nodeRadius + 10, Math.min(innerWidth - nodeRadius - 10, d.x));
                d.y = Math.max(innerTop, Math.min(innerBottom, d.y));
            });

            linkSelection
                .attr("x1", function (d) { return d.source.x; })
                .attr("y1", function (d) { return d.source.y; })
                .attr("x2", function (d) { return shortenLine(d.source, d.target, nodeRadius + 8).x; })
                .attr("y2", function (d) { return shortenLine(d.source, d.target, nodeRadius + 8).y; });

            nodeSelection
                .attr("transform", function (d) {
                    return "translate(" + d.x + "," + d.y + ")";
                });

            // Update cross-layer connector paths (edge of node → edge of badge)
            if (connectors.length > 0) {
                connectorSelection.attr("d", function (d) {
                    var node = nodeMap[d.fileId];
                    if (!node || node.x == null) return "";

                    var nx = node.x;
                    var ny = node.y;
                    var bx = d.badge.x;
                    var by = d.badge.y;

                    // Offset start from edge of file node circle
                    var dx = bx - nx;
                    var dy = by - ny;
                    var dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 1) return "";
                    var sx = nx + (dx / dist) * nodeRadius;
                    var sy = ny + (dy / dist) * nodeRadius;

                    // Offset end to edge of badge pill
                    var ex, ey;
                    if (d.badge.position === "above") {
                        ex = bx;
                        ey = by + badgeH / 2;
                    } else if (d.badge.position === "below") {
                        ex = bx;
                        ey = by - badgeH / 2;
                    } else {
                        var lblText = d.badge.layer + " (" + (d.badge.totalCount || 0) + ")";
                        ex = bx - (lblText.length * 3.5 + 12);
                        ey = by;
                    }

                    if (d.badge.position === "above") {
                        var cy1 = sy - (sy - ey) * 0.5;
                        return "M" + sx + "," + sy +
                            " C" + sx + "," + cy1 +
                            " " + ex + "," + (ey + 20) +
                            " " + ex + "," + ey;
                    } else if (d.badge.position === "below") {
                        var cy2 = sy + (ey - sy) * 0.5;
                        return "M" + sx + "," + sy +
                            " C" + sx + "," + cy2 +
                            " " + ex + "," + (ey - 20) +
                            " " + ex + "," + ey;
                    } else {
                        var cx1 = sx + (ex - sx) * 0.5;
                        var cx2 = sx + (ex - sx) * 0.7;
                        return "M" + sx + "," + sy +
                            " C" + cx1 + "," + sy +
                            " " + cx2 + "," + ey +
                            " " + ex + "," + ey;
                    }
                });
            }
        }
    }

    /** Shorten a line endpoint by a given distance from the target. */
    function shortenLine(source, target, offset) {
        var dx = target.x - source.x;
        var dy = target.y - source.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) return { x: target.x, y: target.y };
        var ratio = (dist - offset) / dist;
        return {
            x: source.x + dx * ratio,
            y: source.y + dy * ratio
        };
    }

    /** Get the layer color from config or fall back to a default. */
    function layerColor(layerName) {
        if (state.configData && state.configData.layer_colors &&
            state.configData.layer_colors[layerName]) {
            return state.configData.layer_colors[layerName];
        }
        // Fallback deterministic color
        var fallbacks = ["#4A90D9", "#50C878", "#E8A838", "#D94A4A",
            "#9B59B6", "#1ABC9C", "#F39C12", "#E74C3C"];
        var idx = 0;
        for (var i = 0; i < layerName.length; i++) {
            idx = (idx + layerName.charCodeAt(i)) % fallbacks.length;
        }
        return fallbacks[idx];
    }

    /** Define arrow markers for file-level edges. */
    function defineFileArrowMarkers(defs) {
        var types = [
            { name: "import", color: REL_COLORS["import"] },
            { name: "inheritance", color: REL_COLORS["inheritance"] },
            { name: "ownership", color: REL_COLORS["ownership"] },
            { name: "function_call", color: REL_COLORS["function_call"] },
            { name: "violation", color: "#f44336" }
        ];

        types.forEach(function (t) {
            defs.append("marker")
                .attr("id", "file-arrow-" + t.name)
                .attr("viewBox", "0 0 10 10")
                .attr("refX", 10)
                .attr("refY", 5)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,0 L10,5 L0,10 Z")
                .attr("fill", t.color);
        });
    }

    // ------------------------------------------------------------------
    // Level 3: Ratsnest View (radial layout)
    // ------------------------------------------------------------------

    function renderRatsnestView() {
        // Stop any running simulation from Level 2
        if (activeSimulation) {
            activeSimulation.stop();
            activeSimulation = null;
        }

        var fileId = state.selectedFile;
        var layerLabel = state.selectedLayer || "...";
        var fileLabel = fileId ? fileName(fileId) : "...";

        updateBreadcrumb([
            { label: "Layers", action: navigateToLayers },
            { label: layerLabel, action: function () {
                navigateToFiles(state.selectedLayer, null, null);
            }},
            { label: fileLabel, action: function () {} }
        ]);

        var svg = d3.select("#layer-diagram");
        svg.selectAll("*").remove();

        if (!fileId) {
            renderEmptyState(svg, "No file selected.");
            return;
        }

        // Use the file path directly — FastAPI's {file_id:path} expects real slashes
        var url = "/api/file/" + fileId;

        fetchJSON(url).then(function (data) {
            if (!data || !data.focus) {
                renderEmptyState(svg, "File not found: " + fileId);
                return;
            }
            renderRatsnestLayout(svg, data);
        }).catch(function (err) {
            console.error("Failed to load ratsnest data:", err);
            renderEmptyState(svg, "Failed to load file data.");
        });
    }

    function renderRatsnestLayout(svg, data) {
        var container = document.getElementById("viz-container");
        var width = container.clientWidth;
        var height = container.clientHeight;

        svg.attr("viewBox", "0 0 " + width + " " + height);

        // Defs for arrow markers
        var defs = svg.append("defs");
        defineFileArrowMarkers(defs);

        var focus = data.focus;
        var neighbors = data.neighbors || [];
        var edges = data.edges || [];
        var violations = data.violations || [];

        var centerX = width / 2;
        var centerY = height / 2;
        var focusRadius = 30;
        var neighborRadius = 20;

        // Calculate radial positions for neighbors
        var orbitRadius = Math.min(width, height) * 0.32;
        var n = neighbors.length;

        // Position neighbors in a circle around the focus
        var neighborPositions = {};
        neighbors.forEach(function (nb, i) {
            var angle = (2 * Math.PI * i / n) - Math.PI / 2; // start from top
            neighborPositions[nb.id] = {
                x: centerX + orbitRadius * Math.cos(angle),
                y: centerY + orbitRadius * Math.sin(angle)
            };
        });

        // Build violation lookup for edges
        var violationLookup = {};
        violations.forEach(function (v) {
            var key = v.source_node_id + ":" + v.target_node_id;
            violationLookup[key] = v;
            var reverseKey = v.target_node_id + ":" + v.source_node_id;
            violationLookup[reverseKey] = v;
        });

        // Diff overlay: build lookup sets
        var diffAddedNodes = {};
        var diffAddedEdges = {};

        if (state.diffData && state.diffData.enabled && state.diffVisible) {
            (state.diffData.added_nodes || []).forEach(function (nid) {
                diffAddedNodes[nid] = true;
            });
            (state.diffData.added_edges || []).forEach(function (e) {
                diffAddedEdges[e.source + ":" + e.target] = true;
            });
        }

        // Draw groups: edges behind, then nodes
        var edgeGroup = svg.append("g").attr("class", "ratsnest-edges");
        var nodeGroup = svg.append("g").attr("class", "ratsnest-nodes");

        // Draw edges
        edges.forEach(function (edge) {
            var sourceId = edge.source;
            var targetId = edge.target;
            var sourcePos, targetPos;

            if (sourceId === focus.id) {
                sourcePos = { x: centerX, y: centerY };
                targetPos = neighborPositions[targetId];
            } else {
                sourcePos = neighborPositions[sourceId];
                targetPos = { x: centerX, y: centerY };
            }

            if (!sourcePos || !targetPos) return;

            var relType = dominantRelType(edge.relationships);
            var vKey = sourceId + ":" + targetId;
            var violation = violationLookup[vKey] || null;

            // Shorten the line to stop at node edges
            var sourceNodeRadius = (sourceId === focus.id) ? focusRadius : neighborRadius;
            var targetNodeRadius = (targetId === focus.id) ? focusRadius : neighborRadius;

            var shortenedSource = shortenLine(targetPos, sourcePos, sourceNodeRadius);
            var shortenedTarget = shortenLine(sourcePos, targetPos, targetNodeRadius);

            var neighborId = (sourceId === focus.id) ? targetId : sourceId;

            var edgeKey = sourceId + ":" + targetId;
            var isDiffAdded = diffAddedEdges[edgeKey];

            var line = edgeGroup.append("line")
                .attr("class", "ratsnest-edge" + (violation ? " violation-pulse" : "") + (isDiffAdded ? " diff-added" : ""))
                .attr("data-neighbor", neighborId)
                .attr("x1", shortenedSource.x)
                .attr("y1", shortenedSource.y)
                .attr("x2", shortenedTarget.x)
                .attr("y2", shortenedTarget.y)
                .attr("stroke", violation ? "#f44336" : relColor(relType))
                .attr("stroke-width", violation ? 3 : 1.5)
                .attr("marker-end", violation ? "url(#file-arrow-violation)" :
                    "url(#file-arrow-" + relType + ")")
                .on("mouseover", function (event) {
                    var html = '<div class="tt-title">' +
                        escapeHtml(fileName(sourceId)) + ' \u2192 ' +
                        escapeHtml(fileName(targetId)) + '</div>';

                    if (edge.relationships) {
                        edge.relationships.forEach(function (r) {
                            html += '<div class="tt-row">' +
                                '<span class="tt-label">' + escapeHtml(r.type) + ':</span>' +
                                '<span class="tt-value">' +
                                escapeHtml(r.source_symbol) + ' \u2192 ' +
                                escapeHtml(r.target_symbol) +
                                (r.line_number ? ' (L' + r.line_number + ')' : '') +
                                '</span></div>';
                        });
                    }

                    if (violation) {
                        html += '<div class="tt-row"><span class="tt-violation">' +
                            escapeHtml(violation.rule) + '</span></div>';
                        html += '<div class="tt-row"><span class="tt-violation">' +
                            escapeHtml(violation.message) + '</span></div>';
                    }

                    showTooltip(html, event);
                })
                .on("mousemove", positionTooltip)
                .on("mouseout", hideTooltip);

            // Relationship type label at midpoint
            var midX = (shortenedSource.x + shortenedTarget.x) / 2;
            var midY = (shortenedSource.y + shortenedTarget.y) / 2;

            edgeGroup.append("text")
                .attr("class", "ratsnest-edge-label")
                .attr("data-neighbor", neighborId)
                .attr("x", midX)
                .attr("y", midY - 6)
                .text(relType);
        });

        // Draw focus node (center, larger)
        var focusG = nodeGroup.append("g")
            .attr("class", "ratsnest-focus-node")
            .attr("transform", "translate(" + centerX + "," + centerY + ")")
            .on("mouseover", function (event) {
                var html = '<div class="tt-title">' + escapeHtml(fileName(focus.file_path)) + '</div>' +
                    '<div class="tt-row"><span class="tt-label">Path:</span>' +
                    '<span class="tt-value">' + escapeHtml(focus.file_path) + '</span></div>' +
                    '<div class="tt-row"><span class="tt-label">Language:</span>' +
                    '<span class="tt-value">' + escapeHtml(focus.language) + '</span></div>' +
                    '<div class="tt-row"><span class="tt-label">Layer:</span>' +
                    '<span class="tt-value">' + escapeHtml(focus.layer) + '</span></div>';
                if (focus.symbols && focus.symbols.length > 0) {
                    html += '<div class="tt-row"><span class="tt-label">Symbols:</span>' +
                        '<span class="tt-value">' + escapeHtml(focus.symbols.join(", ")) + '</span></div>';
                }
                showTooltip(html, event);
            })
            .on("mousemove", positionTooltip)
            .on("mouseout", hideTooltip);

        focusG.append("circle")
            .attr("r", focusRadius)
            .attr("fill", layerColor(focus.layer))
            .attr("fill-opacity", 0.3)
            .attr("stroke", layerColor(focus.layer))
            .attr("stroke-width", 3);

        focusG.append("text")
            .attr("class", "ratsnest-focus-label")
            .attr("dy", 5)
            .text(fileName(focus.file_path));

        // Layer badge below focus node
        focusG.append("text")
            .attr("class", "ratsnest-focus-layer")
            .attr("dy", focusRadius + 18)
            .text(focus.layer);

        // Draw neighbor nodes (radial)
        neighbors.forEach(function (nb) {
            var pos = neighborPositions[nb.id];
            if (!pos) return;

            var nbG = nodeGroup.append("g")
                .attr("class", "ratsnest-neighbor-node" + (diffAddedNodes[nb.id] ? " diff-added" : ""))
                .attr("data-neighbor", nb.id)
                .attr("transform", "translate(" + pos.x + "," + pos.y + ")")
                .on("click", function () {
                    // Recenter ratsnest on this neighbor
                    state.selectedLayer = nb.layer;
                    navigateToRatsnest(nb.id);
                })
                .on("mouseover", function (event) {
                    var html = '<div class="tt-title">' + escapeHtml(fileName(nb.file_path)) + '</div>' +
                        '<div class="tt-row"><span class="tt-label">Path:</span>' +
                        '<span class="tt-value">' + escapeHtml(nb.file_path) + '</span></div>' +
                        '<div class="tt-row"><span class="tt-label">Language:</span>' +
                        '<span class="tt-value">' + escapeHtml(nb.language) + '</span></div>' +
                        '<div class="tt-row"><span class="tt-label">Layer:</span>' +
                        '<span class="tt-value">' + escapeHtml(nb.layer) + '</span></div>' +
                        '<div class="tt-row"><span class="tt-label">Direction:</span>' +
                        '<span class="tt-value">' + escapeHtml(nb.direction) + '</span></div>';
                    if (nb.symbols && nb.symbols.length > 0) {
                        html += '<div class="tt-row"><span class="tt-label">Symbols:</span>' +
                            '<span class="tt-value">' + escapeHtml(nb.symbols.join(", ")) + '</span></div>';
                    }
                    showTooltip(html, event);

                    // Highlight this neighbor, its edge, and the focus node
                    var svgEl = d3.select("#layer-diagram");
                    applyHighlight(svgEl, function (el) {
                        var dn = el.attr("data-neighbor");
                        if (dn) return dn === nb.id;
                        if (el.classed("ratsnest-focus-node")) return true;
                        return false;
                    });
                })
                .on("mousemove", positionTooltip)
                .on("mouseout", function () {
                    hideTooltip();
                    clearHighlight(d3.select("#layer-diagram"));
                });

            nbG.append("circle")
                .attr("r", neighborRadius)
                .attr("fill", layerColor(nb.layer))
                .attr("fill-opacity", 0.2)
                .attr("stroke", layerColor(nb.layer))
                .attr("stroke-width", 2);

            // Filename label below
            nbG.append("text")
                .attr("class", "ratsnest-neighbor-label")
                .attr("dy", neighborRadius + 16)
                .text(fileName(nb.file_path));

            // Layer badge (colored pill)
            var badgeWidth = nb.layer.length * 7 + 12;
            nbG.append("rect")
                .attr("x", -(badgeWidth / 2))
                .attr("y", -(neighborRadius + 18))
                .attr("width", badgeWidth)
                .attr("height", 14)
                .attr("fill", layerColor(nb.layer))
                .attr("fill-opacity", 0.3)
                .attr("rx", 3)
                .attr("ry", 3);

            nbG.append("text")
                .attr("class", "ratsnest-neighbor-badge")
                .attr("y", -(neighborRadius + 8))
                .text(nb.layer);

            // Direction indicator (small arrow icon)
            var dirSymbol = "";
            if (nb.direction === "inbound") {
                dirSymbol = "\u2190"; // left arrow (pointing to center)
            } else if (nb.direction === "outbound") {
                dirSymbol = "\u2192"; // right arrow (pointing away)
            } else if (nb.direction === "both") {
                dirSymbol = "\u2194"; // bidirectional
            }

            if (dirSymbol) {
                nbG.append("text")
                    .attr("class", "ratsnest-direction")
                    .attr("dy", -2)
                    .attr("dx", neighborRadius + 6)
                    .text(dirSymbol);
            }
        });

        // Show empty state for isolated files
        if (neighbors.length === 0) {
            svg.append("text")
                .attr("class", "ratsnest-empty-hint")
                .attr("x", centerX)
                .attr("y", centerY + focusRadius + 50)
                .attr("text-anchor", "middle")
                .attr("fill", "#8888aa")
                .attr("font-size", "14px")
                .text("No connections found for this file.");
        }
    }

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // ------------------------------------------------------------------
    // Diff overlay helpers
    // ------------------------------------------------------------------

    /** Build a set of "source:target" keys for quick lookup. */
    function buildEdgeKeySet(edges) {
        var keys = {};
        (edges || []).forEach(function (e) {
            keys[e.source + ":" + e.target] = true;
        });
        return keys;
    }

    /** Aggregate file-level diff data into layer-level counts using layer_map. */
    function buildLayerDiffSummary(diffData) {
        var summary = {
            addedFiles: {},    // layer -> count
            removedFiles: {},  // layer -> count
            addedEdges: {},    // "srcLayer:tgtLayer" -> count
            removedEdges: {},  // "srcLayer:tgtLayer" -> count
            newViolations: {}, // "srcLayer:tgtLayer" -> count
            resolvedViolations: {}, // "srcLayer:tgtLayer" -> count
            newLayerViolations: {},  // layer -> count (node-level or intra-layer)
            resolvedLayerViolations: {} // layer -> count
        };

        var lm = diffData.layer_map || {};

        (diffData.added_nodes || []).forEach(function (nid) {
            var layer = lm[nid] || "unclassified";
            summary.addedFiles[layer] = (summary.addedFiles[layer] || 0) + 1;
        });

        (diffData.removed_nodes || []).forEach(function (nid) {
            var layer = lm[nid] || "unclassified";
            summary.removedFiles[layer] = (summary.removedFiles[layer] || 0) + 1;
        });

        (diffData.added_edges || []).forEach(function (e) {
            var sl = lm[e.source] || "unclassified";
            var tl = lm[e.target] || "unclassified";
            if (sl !== tl) {
                var key = sl + ":" + tl;
                summary.addedEdges[key] = (summary.addedEdges[key] || 0) + 1;
            }
        });

        (diffData.removed_edges || []).forEach(function (e) {
            var sl = lm[e.source] || "unclassified";
            var tl = lm[e.target] || "unclassified";
            if (sl !== tl) {
                var key = sl + ":" + tl;
                summary.removedEdges[key] = (summary.removedEdges[key] || 0) + 1;
            }
        });

        (diffData.new_violations || []).forEach(function (v) {
            var sl = lm[v.source_node_id] || "unclassified";
            if (!v.target_node_id || lm[v.target_node_id] === sl) {
                summary.newLayerViolations[sl] = (summary.newLayerViolations[sl] || 0) + 1;
            } else {
                var tl = lm[v.target_node_id] || "unclassified";
                var key = sl + ":" + tl;
                summary.newViolations[key] = (summary.newViolations[key] || 0) + 1;
            }
        });

        (diffData.resolved_violations || []).forEach(function (v) {
            var sl = lm[v.source_node_id] || "unclassified";
            if (!v.target_node_id || lm[v.target_node_id] === sl) {
                summary.resolvedLayerViolations[sl] = (summary.resolvedLayerViolations[sl] || 0) + 1;
            } else {
                var tl = lm[v.target_node_id] || "unclassified";
                var key = sl + ":" + tl;
                summary.resolvedViolations[key] = (summary.resolvedViolations[key] || 0) + 1;
            }
        });

        return summary;
    }

    /** Show or hide the diff banner. */
    function renderDiffBanner() {
        var banner = document.getElementById("diff-banner");
        var summaryEl = document.getElementById("diff-summary");
        var toggleBtn = document.getElementById("diff-toggle");

        if (!state.diffData || !state.diffData.enabled) {
            banner.style.display = "none";
            document.body.classList.remove("diff-active");
            return;
        }

        banner.style.display = "flex";
        document.body.classList.add("diff-active");
        summaryEl.textContent = "Since last snapshot: " + state.diffData.summary;
        toggleBtn.textContent = state.diffVisible ? "Hide Diff" : "Show Diff";

        toggleBtn.onclick = function () {
            state.diffVisible = !state.diffVisible;
            toggleBtn.textContent = state.diffVisible ? "Hide Diff" : "Show Diff";
            // Re-render current view to apply/remove diff overlay
            if (state.view === "layers") {
                renderLayerDiagram();
            } else if (state.view === "files") {
                renderFileView();
            } else if (state.view === "ratsnest") {
                renderRatsnestView();
            }
        };
    }

    // ------------------------------------------------------------------
    // Initialization
    // ------------------------------------------------------------------

    function init() {
        Promise.all([
            fetchJSON("/api/layers"),
            fetchJSON("/api/config"),
            fetchJSON("/api/diff")
        ]).then(function (results) {
            state.layerData = results[0];
            state.configData = results[1];
            state.diffData = results[2];

            renderDiffBanner();

            // Handle hash-based routing
            window.addEventListener("hashchange", handleHashChange);

            // Initial render based on current hash
            if (window.location.hash && window.location.hash !== "#") {
                handleHashChange();
            } else {
                renderLayerDiagram();
            }
        }).catch(function (err) {
            console.error("Failed to load data:", err);
            var svg = d3.select("#layer-diagram");
            svg.selectAll("*").remove();
            renderEmptyState(svg, "Failed to load data from API. Is the server running?");
        });

        // Re-render on window resize, but skip if a drag is active
        var resizeTimer;
        var dragging = false;
        window._rubiconDrag = {
            get active() { return dragging; },
            set active(v) { dragging = v; }
        };
        window.addEventListener("resize", function () {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(function () {
                if (window._rubiconDrag.active) return;
                if (state.view === "layers") {
                    renderLayerDiagram();
                } else if (state.view === "files") {
                    renderFileView();
                } else if (state.view === "ratsnest") {
                    renderRatsnestView();
                }
            }, 200);
        });
    }

    // Start the app
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
