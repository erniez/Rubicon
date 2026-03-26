# Rubicon

**Keep your AI agents coloring inside the lines.**

When AI agents write code, they move fast — but they don't always respect your architecture. Rubicon watches your codebase, enforces layer boundaries, and catches structural violations before they compound. Define your architecture once, and Rubicon makes sure every commit stays within the boundaries.

Is your codebase already a hot mess? Rubicon can take snapshots of your architecture. Use diff mode to see what changed since the last snapshot — new dependencies, new violations, resolved violations. Track your cleanup progress over time.

Supports 11 languages out of the box, with basic import detection for others.

## What it does

- **Parses** imports, inheritance, and ownership relationships using Tree-sitter (11 languages) with regex fallback for others
- **Classifies** files into architectural layers by directory and file name patterns
- **Checks** 8 built-in design rules plus user-defined custom rules
- **Visualizes** the architecture as an interactive browser diagram with three-level drill-down

## Quick start

```bash
pip install -e .
rubicon init .
rubicon analyze . --serve
```

1. `rubicon init` scans your project and walks you through assigning directories to layers
2. `rubicon analyze --serve` opens an interactive architecture diagram in your browser
3. Violations are highlighted in red — click to drill down

## Configuration

Rubicon reads a `.rubicon` YAML file in your project root:

```yaml
layers:
  presentation:
    directories:
      - ui/
      - screens/
    color: "#4A90D9"

  domain:
    directories:
      - domain/
    patterns:              # classify files by name, regardless of directory
      - "*Interactor*"
      - "*UseCase*"
    color: "#50C878"

  data:
    directories:
      - data/
    color: "#E8A838"

layer_order:
  - presentation
  - domain
  - data
  - [networking, utilities]  # grouped layers sit side-by-side

rules:
  - no_upward_dependency
  - no_layer_skipping
  - inheritance_flows_downward
  - no_circular_ownership
  - no_circular_imports
  - dependency_inversion
  - single_responsibility
  - orphan_detection

custom_rules:
  - name: "viewmodels_in_presentation"
    pattern: "*ViewModel*"
    layer: presentation
    message: "ViewModels must live in the presentation layer"
    severity: warning

  - name: "no_database_in_domain"
    source_layer: domain
    forbidden_imports:
      - sqlalchemy
      - django.db
    message: "Domain layer must not import database packages"
```

## CLI commands

### `rubicon init [path]`

Interactive setup. Scans for source files, prompts for layer assignments, generates `.rubicon`.

### `rubicon analyze <path>`

Analyze architecture and report violations.

| Flag | Description |
|------|-------------|
| `--serve` | Open interactive visualization in browser |
| `--export` | Export architecture diagram as SVG |
| `--format mermaid` | Output Mermaid diagram text |
| `--snapshot` | Save a snapshot for future diffs |
| `--diff` | Compare against last snapshot, show changes |
| `--diff-against <ref>` | Compare against a specific snapshot |
| `--output <file>` | Write output to file |

### `rubicon check <path>`

CI-friendly mode. Compact output, no snapshots, non-zero exit on violations.

```bash
rubicon check . --fail-on warning   # default
rubicon check . --fail-on error     # only fail on errors
rubicon check . --fail-on info      # strict: fail on anything
```

## Supported languages

| Language | Parser | Relationships |
|----------|--------|---------------|
| Python | Tree-sitter | imports, inheritance, ownership |
| TypeScript/TSX | Tree-sitter | imports, inheritance, ownership |
| Kotlin | Tree-sitter | imports, inheritance, ownership |
| Swift | Tree-sitter | imports, inheritance, ownership |
| Java | Tree-sitter | imports, inheritance, ownership |
| Go | Tree-sitter | imports, struct embedding, ownership |
| Rust | Tree-sitter | use declarations, trait impls, ownership |
| C# | Tree-sitter | using directives, inheritance, ownership |
| C | Tree-sitter | #include, struct ownership |
| C++ | Tree-sitter | #include, inheritance, ownership |
| Ruby | Tree-sitter | require, inheritance, ownership |
| *Others* | Regex fallback | imports only |

## Built-in rules

| Rule | Severity | Description |
|------|----------|-------------|
| `no_upward_dependency` | WARNING | Lower layers must not import from higher layers |
| `no_layer_skipping` | WARNING | Layers must not skip intermediate layers |
| `inheritance_flows_downward` | ERROR | Inheritance must flow from higher to lower layers |
| `no_circular_ownership` | ERROR | No cycles in ownership relationships |
| `no_circular_imports` | WARNING | No cycles in import relationships |
| `dependency_inversion` | INFO | Cross-layer inheritance should target abstractions |
| `single_responsibility` | INFO | Files connecting to 4+ layers may have too many concerns |
| `orphan_detection` | INFO | Files with no connections may be dead code |

## Example projects

The `examples/` directory contains sample projects you can analyze to see Rubicon in action.

### `examples/ecommerce/`

A multi-layer e-commerce app with five layers: presentation, domain (services + models), data, networking, and utilities. This project is intentionally messy — it has upward dependencies, layer skipping, orphaned files, and single-responsibility issues. A good example of what a real-world codebase looks like before cleanup:

```bash
rubicon analyze examples/ecommerce/ --serve
```

### `examples/todo_tracker/`

A TODO list tracker that demonstrates how violations creep in during feature development. The project started clean — then a category feature was added with two architectural shortcuts:

- **The data layer reaches up to the domain layer** — `data/category_store.py` imports `TodoService` from the services layer, violating `no_upward_dependency`
- **The UI layer skips straight to the data layer** — `ui/app.py` imports `CategoryStore` directly instead of going through a service, violating `no_layer_skipping`

Use snapshot + diff to see exactly what changed:

```bash
rubicon analyze examples/todo_tracker/ --snapshot   # baseline
# ... make changes ...
rubicon analyze examples/todo_tracker/ --diff       # see new violations
```

## CI integration

```yaml
# .github/workflows/architecture.yml
name: Architecture Check
on: [pull_request]

jobs:
  rubicon:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install rubicon
      - run: rubicon check . --fail-on warning
```

## Visualization

The interactive visualization has three levels:

1. **Layer blocks** — strata diagram showing layers, connection counts, and violations
2. **File-level** — force-directed graph of files within or between layers
3. **Ratsnest** — radial view of a single file and all its connections

## License

MIT
