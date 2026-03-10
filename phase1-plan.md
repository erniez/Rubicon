# Phase 1 Execution Plan — Core Engine

Each step produces a working, testable increment. Verification commands assume you're in the project root.

---

## Step 1: Project Scaffold

**Build:** `pyproject.toml` with all Phase 1 dependencies, package structure with `__init__.py` files, and `cli.py` with Typer wired up. A single `rubicon <path>` command that prints the resolved path and exits.

**Verify:**
```bash
# Install in dev mode
pip install -e ".[dev]"

# CLI responds and shows help
rubicon --help

# Accepts a path argument without crashing
rubicon .

# pytest runs (no tests yet, but the harness works)
pytest
```

**Done when:** `rubicon .` prints the target path and exits cleanly.

---

## Step 2: File Crawler

**Build:** `crawler/scanner.py` (file discovery, language detection via extension map) and `crawler/ignore.py` (.gitignore parsing + default excludes like `node_modules/`, `build/`, `__pycache__/`).

**Verify:**
```bash
# Unit tests with a small fixture directory
pytest tests/test_crawler.py -v

# Smoke test: crawl Rubicon's own repo
rubicon . --crawl-only
# Should list every .py and .md file, skipping .git/ and __pycache__/
```

**Test fixtures to create:**
- `tests/fixtures/sample_project/` with a mix of `.py`, `.ts`, `.kt` files, a `.gitignore`, and directories that should be excluded (`node_modules/`, `build/`).

**Done when:** Crawler returns correct `SourceFile` list for the fixture project, respects `.gitignore`, and the `--crawl-only` flag prints discovered files to the terminal.

---

## Step 3: Data Models

**Build:** `graph/models.py` — dataclasses for `Node`, `Edge`, `Relationship`, `Violation`, `SourceFile`. Enums for `RelationshipType`, `Severity`, `Language`.

**Verify:**
```bash
# Unit tests: construct each model, check field types, test enum membership
pytest tests/test_models.py -v

# Spot check: import from a Python REPL
python -c "from rubicon.graph.models import Node, RelationshipType; print(RelationshipType.IMPORT)"
```

**Done when:** All models instantiate cleanly, enums are complete, and type checkers (mypy) pass on the models file.

---

## Step 4: Tree-sitter Parser + Python Adapter

**Build:** `parser/base.py` (Protocol class defining the adapter interface), `parser/treesitter.py` (driver that loads the right adapter per language), `parser/adapters/python.py` (extracts imports, inheritance, ownership from Python files).

**Verify:**
```bash
# Unit tests against fixture files
pytest tests/test_parser_python.py -v
```

**Test fixtures to create** (`tests/fixtures/python/`):
- `simple_import.py` — `import os`, `from pathlib import Path` → expect IMPORT relationships
- `class_inheritance.py` — `class Dog(Animal):` → expect INHERITANCE edge from Dog to Animal
- `ownership.py` — `class Car: engine: Engine` → expect OWNERSHIP edge from Car to Engine
- `mixed.py` — combination of all three → expect all relationship types extracted
- `parse_error.py` — intentionally broken syntax → expect graceful skip with warning, no crash

**Done when:** Parser extracts correct `Relationship` objects for all three relationship types from fixture files, and broken files produce warnings instead of crashes.

---

## Step 5: TypeScript, Kotlin, and Swift Adapters

**Build:** `parser/adapters/typescript.py`, `parser/adapters/kotlin.py`, and `parser/adapters/swift.py`, same interface as the Python adapter.

**Verify:**
```bash
pytest tests/test_parser_typescript.py -v
pytest tests/test_parser_kotlin.py -v
pytest tests/test_parser_swift.py -v
```

**Test fixtures to create** (`tests/fixtures/typescript/` and `tests/fixtures/kotlin/`):

TypeScript:
- `import_variants.ts` — `import { Foo } from './foo'`, `import * as bar from 'bar'`, `require('baz')` → IMPORT edges
- `class_extends.ts` — `class Dog extends Animal implements Pet` → INHERITANCE edges
- `ownership.ts` — `class Car { engine: Engine }` → OWNERSHIP edge

Kotlin:
- `import_variants.kt` — `import com.example.Foo` → IMPORT edge
- `class_hierarchy.kt` — `class Dog : Animal(), Pet` → INHERITANCE edges
- `ownership.kt` — `class Car(val engine: Engine)` → OWNERSHIP edge

Swift (`tests/fixtures/swift/`):
- `import_variants.swift` — `import Foundation`, `import UIKit` → IMPORT edges
- `class_hierarchy.swift` — `class Dog: Animal`, `class Cat: Animal, Pet` (protocol conformance) → INHERITANCE edges
- `ownership.swift` — `class Car { var engine: Engine }`, `struct Garage { let car: Car }` → OWNERSHIP edges
- `struct_and_enum.swift` — structs and enums with relationships → verify extraction beyond classes

**Done when:** Each adapter extracts all three relationship types from its language's fixture files.

---

## Step 6: Graph Builder

**Build:** `graph/builder.py` (assembles NetworkX digraph from parser output) and `graph/layered.py` (reads layer config, tags nodes).

**Verify:**
```bash
pytest tests/test_graph_builder.py -v
```

**Test strategy:**
- Feed the builder a known set of `Relationship` objects → assert correct nodes and edges in the resulting NetworkX graph
- Check that multiple relationships between the same two files consolidate into a single edge with multiple relationship entries
- Feed a layer config → assert nodes get the correct `layer` attribute
- Feed a file not covered by any layer → assert it gets tagged as `unclassified`

**Integration smoke test:**
```bash
# End-to-end: crawl fixtures → parse → build graph → print node/edge counts
rubicon tests/fixtures/sample_project/ --graph-only
# Should output something like: "12 nodes, 18 edges (8 import, 5 inheritance, 5 ownership)"
```

**Done when:** Graph accurately represents the parsed relationships, and layer tagging works from config.

---

## Step 7: Config Reader

**Build:** `classifier/config.py` — parse `.rubicon` YAML for layer definitions, layer order, and enabled rules.

**Verify:**
```bash
pytest tests/test_config.py -v
```

**Test strategy:**
- Parse the example `.rubicon` from the architecture doc → assert correct layer→directory mappings, layer order, and rule list
- Missing file → return sensible defaults (no layers, all rules enabled)
- Malformed YAML → clear error message pointing to the problem

**Done when:** Config loads correctly from the sample `.rubicon` file and handles edge cases without crashing.

---

## Step 8: Rule Engine + All 6 Built-in Rules

**Build:** `rules/engine.py` (runs all enabled rules, collects violations) and `rules/builtin.py` (implements all 6 rules).

**Verify:**
```bash
pytest tests/test_rules.py -v
```

**Each rule gets two test cases minimum:**

| Rule | Clean case (no violations) | Violation case |
|------|---------------------------|----------------|
| `no_upward_dependency` | presentation → domain import | data → presentation import |
| `no_layer_skipping` | presentation → domain → data | presentation → data (skipping domain) |
| `inheritance_flows_downward` | domain class extends data class | data class extends presentation class |
| `no_circular_ownership` | A owns B owns C (no cycle) | A owns B owns C owns A |
| `single_responsibility` | file touches 2 layers | file touches 5 layers |
| `orphan_detection` | file with edges | file with zero edges |

**Integration smoke test:**
```bash
# Crawl a fixture project with known violations → verify they appear in output
rubicon tests/fixtures/violation_project/
# Should print violations grouped by severity
```

**Done when:** All 6 rules correctly detect their violation condition and return clean results for valid architectures. Running against the fixture project prints accurate, specific violations.

---

## Step 9: Terminal Reporter

**Build:** Color-coded terminal output — violations grouped by severity (ERROR → WARNING → INFO), showing file paths, line numbers, and rule names. Summary counts at the end.

**Verify:**
```bash
# Visual check: run against the violation fixture project
rubicon tests/fixtures/violation_project/

# Expected output structure:
# ERRORS (2)
#   ✗ no_circular_ownership: A.py → B.py → C.py → A.py
#   ✗ inheritance_flows_downward: data/Repo.py inherits from presentation/View.py
# WARNINGS (1)
#   ⚠ no_upward_dependency: data/Store.py imports presentation/Screen.py (line 3)
# INFO (1)
#   ℹ orphan_detection: utils/unused.py has no connections
#
# Summary: 2 errors, 1 warning, 1 info

# Non-zero exit code when errors exist
rubicon tests/fixtures/violation_project/; echo "Exit code: $?"
# Should print "Exit code: 1"

# Zero exit code for clean project
rubicon tests/fixtures/clean_project/; echo "Exit code: $?"
# Should print "Exit code: 0"
```

**Done when:** Output is readable, color-coded, and the exit code reflects whether errors were found (useful for future CI integration).

---

## Step 10: Mermaid Diagram Output

**Build:** Generate a Mermaid layer diagram — layers as boxes, edges with connection counts, violation annotations.

**Verify:**
```bash
# Generate Mermaid output
rubicon tests/fixtures/sample_project/ --format mermaid

# Should output valid Mermaid syntax like:
# graph TD
#     presentation["Presentation (4 files)"] -->|"12 imports"| domain["Domain (3 files)"]
#     domain -->|"5 imports"| data["Data (3 files)"]
#     presentation -.->|"⚠ 2 violations"| data

# Validate: paste output into https://mermaid.live or render locally
npx -y @mermaid-js/mermaid-cli mmdc -i output.mmd -o output.svg

# Also write to file
rubicon tests/fixtures/sample_project/ --format mermaid --output architecture.mmd
test -f architecture.mmd && echo "File created"
```

**Done when:** Output is valid Mermaid syntax that renders correctly, shows all layers with file counts, edges with relationship counts, and violation annotations.

---

## End-to-End Acceptance Test

After all steps are complete, the full pipeline should work:

```bash
# Point Rubicon at a real project with a .rubicon config
rubicon /path/to/real/project/

# Expected behavior:
# 1. Crawls all source files, skipping ignored paths
# 2. Parses Python, TypeScript, and Kotlin files for imports, inheritance, ownership
# 3. Builds the dependency graph
# 4. Reads .rubicon config for layer assignments
# 5. Runs all 6 rules
# 6. Prints color-coded violations to terminal
# 7. Exits with code 1 if errors found, 0 if clean

# Mermaid output for the same project
rubicon /path/to/real/project/ --format mermaid --output arch.mmd
```

The ultimate dogfood test: point Rubicon at its own repo with a `.rubicon` config and verify the output makes sense.
