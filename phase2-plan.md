# Phase 2 Execution Plan — Interactive Visualization + Diff

Each step produces a working, testable increment. Verification commands assume you're in the project root.

Phase 2 builds on top of the complete Phase 1 core engine: CLI, file crawler, Tree-sitter parsers (Python, TypeScript, Kotlin, Swift), graph builder, layer tagging, all 8 built-in rules, terminal reporter, and Mermaid output. It adds four major capabilities: a FastAPI visualization server, a D3.js interactive browser UI with three-level drill-down, a snapshot engine for persisting graph state, and a diff mode for comparing snapshots.

---

## Step 1: Add Phase 2 Dependencies

**Build:** Update `pyproject.toml` to add `fastapi>=0.100` and `uvicorn[standard]>=0.23` to the dependencies list. These are already listed in CLAUDE.md as project dependencies but are not yet in `pyproject.toml`.

**Verify:**
```bash
# Reinstall in dev mode
pip install -e ".[dev]"

# Confirm FastAPI and uvicorn are importable
python -c "import fastapi; import uvicorn; print('OK')"

# Confirm Phase 1 still works
rubicon --help
pytest
```

**Done when:** `pip install -e ".[dev]"` succeeds, both packages import, and all existing Phase 1 tests still pass.

---

## Step 2: Snapshot Data Model

**Build:** `snapshot/models.py` — a `Snapshot` dataclass that captures the full graph state at a point in time:

```python
@dataclass
class Snapshot:
    timestamp: datetime
    commit_hash: str | None       # from git rev-parse HEAD, None if not a git repo
    nodes: list[dict]             # serialized node attributes (id, file_path, language, layer, symbols)
    edges: list[dict]             # serialized edge data (source, target, relationships)
    violations: list[dict]        # serialized Violation objects
    layer_map: dict[str, str]     # file_path → layer for every node
```

Add serialization helpers: `graph_to_snapshot(graph, violations, config) -> Snapshot` and `snapshot_to_dict(snapshot) -> dict` / `dict_to_snapshot(data) -> Snapshot` for JSON round-tripping. Relationships within edges must serialize their `RelationshipType` enum and `Path` fields to strings and deserialize them back.

**Verify:**
```bash
pytest tests/test_snapshot_models.py -v
```

**Test strategy:**
- Build a small graph from Phase 1's `build_graph_from_relationships`, run rules, create a snapshot → assert all fields populated
- Round-trip test: `snapshot_to_dict` → `dict_to_snapshot` → assert equality with original
- Test with `commit_hash=None` (non-git repo) → no crash
- Test with empty graph (0 nodes, 0 edges) → valid snapshot

**Done when:** Snapshots serialize to JSON-safe dicts and deserialize back to identical `Snapshot` objects, including relationship types and file paths.

---

## Step 3: Snapshot Store (Save / Load)

**Build:** `snapshot/store.py` — functions to persist and retrieve snapshots:
- `save_snapshot(root: Path, snapshot: Snapshot) -> Path` — writes to `.rubicon/snapshots/{timestamp}.json`, creates the directory if needed, returns the file path
- `load_latest_snapshot(root: Path) -> Snapshot | None` — finds the most recent snapshot file, returns `None` if no snapshots exist
- `load_snapshot(path: Path) -> Snapshot` — loads a specific snapshot file
- `list_snapshots(root: Path) -> list[Path]` — returns all snapshot files sorted by timestamp

Use `git rev-parse HEAD` (subprocess) to capture the commit hash, falling back to `None` if it fails.

**Verify:**
```bash
pytest tests/test_snapshot_store.py -v
```

**Test strategy (using `tmp_path` fixture):**
- Save a snapshot → assert `.rubicon/snapshots/` directory created, JSON file exists, is valid JSON
- Save two snapshots → `load_latest_snapshot` returns the second one
- Load from empty directory → returns `None`
- Round-trip: save → load → assert snapshot data matches
- `list_snapshots` returns files in chronological order

**Done when:** Snapshots save to disk as JSON, load back faithfully, and latest-snapshot lookup works correctly.

---

## Step 4: Snapshot Diff Engine

**Build:** `snapshot/diff.py` — compare two snapshots and produce a structured diff:

```python
@dataclass
class SnapshotDiff:
    added_edges: list[dict]       # edges in current but not in previous
    removed_edges: list[dict]     # edges in previous but not in current
    added_nodes: list[str]        # node IDs new in current
    removed_nodes: list[str]      # node IDs gone from current
    new_violations: list[dict]    # violations in current but not in previous
    resolved_violations: list[dict]  # violations in previous but not in current
    summary: str                  # e.g. "+12 connections, -3 connections, 2 new violations"
```

- `diff_snapshots(previous: Snapshot, current: Snapshot) -> SnapshotDiff`
- Edge comparison by `(source, target, relationship_type)` tuple — ignore line number changes
- Violation comparison by `(rule, source_node_id, target_node_id)` tuple — ignore message text changes

**Verify:**
```bash
pytest tests/test_snapshot_diff.py -v
```

**Test fixtures to create** (`tests/fixtures/snapshots/`):
- `baseline.json` — snapshot with 5 nodes, 6 edges, 1 violation
- `added_edge.json` — same as baseline + 1 new edge → diff shows 1 added edge
- `removed_edge.json` — same as baseline - 1 edge → diff shows 1 removed edge
- `new_violation.json` — same as baseline + 1 new violation → diff shows 1 new violation
- `resolved_violation.json` — same as baseline - 1 violation → diff shows 1 resolved violation
- `identical.json` — exact copy of baseline → diff shows no changes

**Tests:**
- Diff baseline vs added_edge → `added_edges` has 1 entry, everything else empty
- Diff baseline vs removed_edge → `removed_edges` has 1 entry
- Diff baseline vs new_violation → `new_violations` has 1 entry
- Diff baseline vs resolved_violation → `resolved_violations` has 1 entry
- Diff baseline vs identical → all lists empty, summary says "No changes"
- Diff `None` vs current (first run, no previous) → everything counted as "added"
- Summary string is human-readable and matches the counts

**Done when:** Diff engine correctly identifies added/removed edges and new/resolved violations across all fixture pairs.

---

## Step 5: Wire Snapshot + Diff into CLI

**Build:** Update `cli.py`:
- After running rules, always save a snapshot (call `save_snapshot`)
- Add `--diff` flag: load the latest previous snapshot, run `diff_snapshots`, and include diff data in the output
- Add `--no-snapshot` flag: skip saving (useful for CI or quick checks)
- Update the terminal reporter to show diff information when present: a banner line at the top ("Since last snapshot: +N connections, -N connections, K new violations, J resolved"), and markers on individual violations indicating [NEW] or [RESOLVED]

**Verify:**
```bash
# First run: saves a snapshot
rubicon tests/fixtures/sample_project/
ls .rubicon/snapshots/
# Should have 1 JSON file

# Second run with --diff: compares against first
rubicon tests/fixtures/sample_project/ --diff
# Should show "Since last snapshot: No changes" (nothing changed)

# Modify a fixture, run again with --diff → see added/removed connections

# --no-snapshot flag
rubicon tests/fixtures/sample_project/ --no-snapshot
ls .rubicon/snapshots/
# Should still have only 1 file from before

# Exit codes unchanged: still 1 on errors, 0 on clean
```

**Done when:** Snapshots auto-save on each run, `--diff` shows a comparison banner, and `--no-snapshot` suppresses saving.

---

## Step 6: Graph JSON Serialization API

**Build:** `viz/api.py` — functions that transform the in-memory graph + violations into JSON structures for the D3.js frontend. These are pure functions, no FastAPI dependency yet:

- `layer_summary(graph, config, violations) -> dict` — Level 1 data: list of layers with file counts and colors, inter-layer edge counts with relationship breakdowns, inter-layer violation counts
- `file_level_view(graph, config, violations, layer: str | None, source_layer: str | None, target_layer: str | None) -> dict` — Level 2 data: nodes within the specified layer(s) with their file paths, languages, and symbols; edges between those nodes with relationship types; violations involving those nodes
- `ratsnest_view(graph, config, violations, file_id: str) -> dict` — Level 3 data: the focus node plus all directly connected nodes (inbound and outbound), all edges involving the focus node, relationship types color-coded, violations on those edges
- `diff_overlay(diff: SnapshotDiff | None) -> dict` — overlay data for any view level: added/removed edges, new/resolved violations, summary banner text

**Verify:**
```bash
pytest tests/test_viz_api.py -v
```

**Test strategy:**
- Build a graph with 3 layers (presentation, domain, data), multiple files per layer, known inter-layer edges
- `layer_summary` → assert correct layer count, file counts match, edge counts match, violation counts match
- `file_level_view(layer="domain")` → returns only domain files and their edges
- `file_level_view(source_layer="presentation", target_layer="domain")` → returns files from both layers and only cross-layer edges
- `ratsnest_view(file_id="app/ui/Screen.py")` → returns the focus node + all neighbors, both in and out
- `diff_overlay(None)` → returns empty overlay (no diff mode)
- `diff_overlay(diff)` → returns correctly structured overlay data

**Done when:** All three view-level functions return correctly structured JSON-serializable dicts for known graph inputs.

---

## Step 7: FastAPI Server Shell

**Build:** `viz/server.py` — a FastAPI application that:
- Serves static files from `viz/static/` at `/`
- Exposes JSON API endpoints:
  - `GET /api/layers` → calls `layer_summary`, returns JSON
  - `GET /api/files?layer=X` or `GET /api/files?source_layer=X&target_layer=Y` → calls `file_level_view`
  - `GET /api/file/{file_id:path}` → calls `ratsnest_view`
  - `GET /api/diff` → calls `diff_overlay` (returns empty if no diff data)
  - `GET /api/config` → returns layer colors, layer order, rule names
- The server receives the graph, config, violations, and optional diff at startup (passed via module-level state or a startup event — keep it simple, no dependency injection framework)
- Add a `start_server(graph, config, violations, diff, port)` function that `cli.py` will call

Update `cli.py`:
- Add `--serve` flag (or make it the default for the `visualize` subcommand): starts the server and opens the browser
- Add `--port` option (default 8742)

**Verify:**
```bash
# Start the server against the sample project
rubicon tests/fixtures/sample_project/ --serve &
SERVER_PID=$!

# Test API endpoints
curl -s http://localhost:8742/api/layers | python -m json.tool
# Should return valid JSON with layer data

curl -s http://localhost:8742/api/files?layer=domain | python -m json.tool
# Should return files in the domain layer

curl -s "http://localhost:8742/api/file/app/models/user.py" | python -m json.tool
# Should return ratsnest data for that file

curl -s http://localhost:8742/api/config | python -m json.tool
# Should return layer colors and order

# Clean up
kill $SERVER_PID

# Automated tests
pytest tests/test_viz_server.py -v
```

**Test strategy (using FastAPI TestClient):**
- `GET /api/layers` → 200, valid JSON, contains expected layers
- `GET /api/files?layer=nonexistent` → 200, empty file list (not 404)
- `GET /api/file/nonexistent.py` → 404
- `GET /api/config` → 200, contains layer_order and colors

**Done when:** All API endpoints return correct JSON, static files are served, and the server starts from the CLI with `--serve`.

---

## Step 8: D3.js Level 1 — Layer Block Diagram

**Build:** `viz/static/index.html`, `viz/static/styles.css`, and `viz/static/app.js`. Start with the Level 1 view:

- Fetch `/api/layers` on page load
- Render layers as rectangular blocks using D3.js (not force-directed — use a grid or hierarchical layout following `layer_order`)
- Block size proportional to file count
- Layer colors from config (`/api/config`)
- Edges between layers as curved arrows with connection count labels
- Edge thickness proportional to connection count
- Edge color: green = all clean, yellow = has warnings, red = has errors
- File count label inside each block
- Layer name as block header
- Click a layer block → transition to Level 2 (file view within that layer)
- Click an inter-layer edge → transition to Level 2 (file view between those two layers)

**Verify:**
```bash
# Start server with a multi-layer project
rubicon tests/fixtures/violation_project/ --serve

# In browser at http://localhost:8742:
# 1. See layer blocks arranged in order
# 2. See edges with counts between layers
# 3. Violation edges are red/yellow
# 4. Click a layer → navigates (will be blank until Step 9, but URL changes)
# 5. Click an edge → navigates
```

**Test fixtures needed:**
- `tests/fixtures/viz_project/` — a small multi-layer project with:
  - `app/ui/screen.py` and `app/ui/widget.py` (presentation)
  - `app/models/user.py` and `app/models/order.py` (domain)
  - `app/db/repo.py` and `app/db/store.py` (data)
  - `app/api/client.py` (networking)
  - A `.rubicon` config mapping these directories to layers
  - Known import/inheritance/ownership relationships between layers
  - At least one violation (e.g. data → presentation import)

**Done when:** Browser shows a layer block diagram with correctly colored blocks and edges, connection counts are accurate, and clicking navigates (even if target view is not yet built).

---

## Step 9: D3.js Level 2 — File-Level View

**Build:** Extend `app.js` with the Level 2 view:

- Fetch `/api/files?layer=X` (single layer drill-down) or `/api/files?source_layer=X&target_layer=Y` (inter-layer drill-down)
- Render individual files as nodes using D3.js force-directed layout
- Node labels show filename (not full path — show path on hover tooltip)
- Edges between files labeled with relationship type:
  - Blue lines = import
  - Orange lines = inheritance
  - Purple lines = ownership
- Violation edges highlighted: thick red border + violation icon
- Click a violation edge → show a tooltip with rule name and message
- Click a file node → transition to Level 3 (ratsnest view)
- Breadcrumb navigation at top: "Layers > Domain" or "Layers > Presentation → Domain"
- Back button / breadcrumb click → return to Level 1

**Verify:**
```bash
# Start server with viz_project
rubicon tests/fixtures/viz_project/ --serve

# In browser:
# 1. Click a layer → see files in that layer as force-directed nodes
# 2. Edges are color-coded by relationship type
# 3. Violation edges are highlighted red
# 4. Hovering a violation edge shows rule + message
# 5. Click "Layers" breadcrumb → returns to Level 1
# 6. Click an inter-layer edge from Level 1 → see files from both layers
# 7. Click a file node → navigates (will be blank until Step 10, but URL changes)
```

**Done when:** File-level view renders correctly with color-coded edges, violation highlighting, and working breadcrumb navigation back to Level 1.

---

## Step 10: D3.js Level 3 — Ratsnest View

**Build:** Extend `app.js` with the Level 3 view:

- Fetch `/api/file/{file_id}` for the focus file
- Render the focus node at center, all connected nodes (inbound and outbound) arranged radially
- Edge direction shown with arrows (inbound arrows point to center, outbound arrows point away)
- Color-coded by relationship type (same as Level 2: blue/orange/purple)
- Violation edges pulsate red (CSS animation)
- Each connected node shows: filename, layer badge (colored pill), relationship type label on the edge
- Click any connected node → recenter the ratsnest on that node (re-fetch `/api/file/{new_id}`)
- Breadcrumb: "Layers > Domain > user.py" — click any level to navigate back
- Hover a node → tooltip with full file path, language, layer
- Hover an edge → tooltip with relationship type, source symbol, target symbol, line number

**Verify:**
```bash
# Start server with viz_project
rubicon tests/fixtures/viz_project/ --serve

# In browser:
# 1. Navigate to Level 3 for app/models/user.py
# 2. See center node with all connections radiating out
# 3. Edges color-coded by type
# 4. Violation edges pulse red
# 5. Click a neighbor → ratsnest recenters on that file
# 6. Breadcrumb works at all levels
# 7. Hover tooltips show full details
```

**Done when:** Ratsnest view shows all connections for a focus file, supports recentering by clicking neighbors, and breadcrumb navigation works through all three levels.

---

## Step 11: Diff Overlay on All Views

**Build:** Extend `app.js` to support diff mode across all three view levels:

- Fetch `/api/diff` on page load — if it returns data, enable diff overlay
- **Summary banner** at the top of every view: "Since last snapshot: +N connections, -N connections, K new violations, J resolved" (styled as a fixed bar)
- **Level 1 diff:** Layer blocks show +/- badges for added/removed files. Inter-layer edges show green dashed style for new connections, gray faded style for removed connections. New violation count as a red pulsing badge, resolved violation count as a green checkmark badge.
- **Level 2 diff:** New file nodes have a green border glow. Removed file nodes shown as ghost nodes (faded gray, dashed border). New edges are green dashed lines. Removed edges are gray dashed lines. New violations get a [NEW] tag. Resolved violations get a [RESOLVED] tag with strikethrough.
- **Level 3 diff:** Same as Level 2, but for the single-file focus view. New connections to the focus file are highlighted green. Removed connections shown as ghosts.
- Add a toggle button to show/hide the diff overlay (useful when it's visually noisy)

Update `cli.py` so that when `--serve` and `--diff` are both passed, the diff data is passed to the server.

**Verify:**
```bash
# First run: create a baseline snapshot
rubicon tests/fixtures/viz_project/

# Modify viz_project to add a new import and remove one
# (add a test helper script that does this)

# Second run with --serve --diff
rubicon tests/fixtures/viz_project/ --serve --diff

# In browser:
# 1. Summary banner shows "+1 connection, -1 connection"
# 2. Level 1: new edge is green dashed, removed edge is gray
# 3. Level 2: new/removed edges styled correctly
# 4. Level 3: same
# 5. Toggle button hides/shows overlay
```

**Test fixtures needed:**
- `tests/fixtures/diff_project_v1/` — baseline state with known edges
- `tests/fixtures/diff_project_v2/` — modified state: 1 new import, 1 removed import, 1 new violation, 1 resolved violation

**Test strategy (for `viz/api.py` diff_overlay):**
- Pass a `SnapshotDiff` with known added/removed edges → assert overlay JSON contains them
- Pass `None` → assert empty overlay
- Level 1 aggregation: diff edges grouped by layer pairs
- Level 2 filtering: diff edges filtered to the viewed layers only
- Level 3 filtering: diff edges filtered to the focus file only

**Done when:** Diff overlay appears on all three view levels with correct styling, the summary banner is accurate, and the toggle button works.

---

## Step 12: Mermaid Output with Diff Annotations

**Build:** Update `mermaid.py` to support diff mode:
- Accept an optional `SnapshotDiff` parameter
- New edges rendered with `-.->` dashed style and "(+NEW)" annotation
- Removed edges rendered with `-.->` gray style and "(-REMOVED)" annotation
- New violations annotated with "(NEW VIOLATION)"
- Summary comment at top: `%% Diff: +N connections, -N connections, K new violations, J resolved`

Update `cli.py` so that `--format mermaid --diff` passes diff data to `generate_mermaid`.

**Verify:**
```bash
# With baseline snapshot already saved
rubicon tests/fixtures/viz_project/ --format mermaid --diff

# Output should contain:
# %% Diff: +1 connection, -1 connection, 1 new violation
# domain -.->|"+1 NEW"| networking
# presentation -.->|"-1 REMOVED"| data

# Validate: paste into mermaid.live
```

**Test strategy:**
```bash
pytest tests/test_mermaid_diff.py -v
```
- Generate mermaid with diff → assert dashed arrows for new/removed edges
- Generate mermaid without diff → assert output identical to Phase 1 behavior (no regression)
- Generate mermaid with empty diff → no diff annotations

**Done when:** Mermaid output includes diff annotations when diff data is present and remains unchanged when it's not.

---

## Step 13: Polish and Edge Cases

**Build:** Handle edge cases and polish the user experience:

1. **Empty project:** Server starts with an empty graph → show a "No files found" message in the browser, not a blank canvas
2. **Single-layer project:** All files in one layer → Level 1 shows one block with intra-layer edge count, Level 2 works normally
3. **No config:** Project with no `.rubicon` file → all nodes "unclassified", single block in Level 1, visualization still works
4. **Large project resilience:** Test with 500+ nodes — ensure the D3.js layout doesn't freeze the browser (use `requestAnimationFrame` throttling in force simulation, limit initial node display, add a "showing N of M files" indicator)
5. **Browser auto-open:** When `--serve` starts, auto-open `http://localhost:{port}` in the default browser using `webbrowser.open`
6. **Graceful shutdown:** Ctrl+C cleanly stops the server with a message
7. **Port conflict:** If the port is in use, try the next port up to port+10, then fail with a clear message
8. **URL routing:** Support direct linking to views via URL hash (e.g. `/#/layer/domain`, `/#/file/app/models/user.py`) so browser back/forward buttons work

**Verify:**
```bash
# Empty project
mkdir /tmp/empty_project
rubicon /tmp/empty_project --serve
# Browser shows "No files found" message

# No config
rubicon tests/fixtures/sample_project/ --serve
# All files in "unclassified" layer, visualization works

# Port conflict
rubicon tests/fixtures/viz_project/ --serve --port 8742 &
rubicon tests/fixtures/viz_project/ --serve --port 8742
# Second instance should find next available port or show clear error

# URL routing
# Navigate to http://localhost:8742/#/layer/domain
# Should go directly to Level 2 domain view
```

**Done when:** All edge cases handled gracefully, browser auto-opens, server shuts down cleanly, and URL routing supports direct linking and back/forward navigation.

---

## End-to-End Acceptance Test

After all steps are complete, the full Phase 2 pipeline should work:

```bash
# 1. First run: analyze, save snapshot, launch browser
rubicon /path/to/real/project/ --serve
# Browser opens with Layer Block Diagram
# Click through all three levels
# Close browser, Ctrl+C server

# 2. Make changes to the project (or simulate agent run)

# 3. Diff run: analyze, compare snapshots, launch browser with overlay
rubicon /path/to/real/project/ --serve --diff
# Browser opens with diff overlay
# Summary banner shows changes
# Navigate all three levels, see diff indicators
# Toggle overlay on/off

# 4. Terminal diff (no browser)
rubicon /path/to/real/project/ --diff
# Terminal output shows violations with [NEW] / [RESOLVED] markers
# Banner: "Since last snapshot: +N connections, -N connections, ..."

# 5. Mermaid diff
rubicon /path/to/real/project/ --format mermaid --diff --output arch-diff.mmd
# Mermaid output with diff annotations

# 6. Snapshot management
ls .rubicon/snapshots/
# Multiple timestamped JSON files

# 7. No snapshot mode
rubicon /path/to/real/project/ --no-snapshot --serve
# Visualization works but no snapshot saved
```

The ultimate dogfood test: run Rubicon on its own codebase with `--serve`, navigate all three levels, then make a code change and run with `--serve --diff` to see the change visualized.
