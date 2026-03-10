# Rubicon

Rubicon is a language-agnostic code architecture visualization and design rule checking tool. It crawls a repository, extracts import/inheritance/ownership relationships using Tree-sitter, classifies files into architectural layers, checks design rules, and renders an interactive browser-based diagram.

## Architecture Reference

See `rubicon-architecture.md` for the full system design, component breakdown, data models, visualization spec, and phased development plan.

## Project Conventions

### Language & Runtime
- Python 3.11+
- Use type hints everywhere — all function signatures, return types, and dataclass fields
- Use dataclasses for all data models (Node, Edge, Relationship, Violation, Snapshot, SourceFile)
- Use enums for fixed sets (RelationshipType, Severity, Language)

### Project Structure
- Follow the directory layout defined in rubicon-architecture.md under "File Structure"
- Each module should have a clear single responsibility
- Keep adapters (per-language Tree-sitter query files) self-contained — one file per language

### Dependencies
- CLI: typer
- Graph: networkx
- Parsing: tree-sitter, plus individual tree-sitter-{language} packages
- Web server: fastapi, uvicorn
- Visualization: D3.js (served as static files, no build step)
- Config: pyyaml
- Use pyproject.toml for dependency management

### Code Style
- No classes where a function will do — prefer functions for stateless operations
- Use dependency injection via function parameters, not globals or singletons
- Parser adapters must implement a common interface (protocol class in base.py)
- All rules in the rule engine must follow the same signature: take the graph, return a list of violations
- Keep the D3.js visualization in a single app.js file — no framework, no build tooling

### Error Handling
- Fail gracefully on unparseable files — log a warning, skip the file, continue
- Never crash on a single bad file — the tool must handle messy real-world repos
- Tree-sitter parse errors should be collected and reported at the end, not thrown

### Testing
- Use pytest
- Every rule in the rule engine must have tests with known-good and known-violation cases
- Parser adapters should have tests using small fixture files per language

### Git
- Conventional commits (feat:, fix:, refactor:, test:, docs:)
- One logical change per commit

## Current Phase

Phase 1 — Core Engine. Focus on:
1. CLI scaffolding with Typer
2. File crawler with language detection and .gitignore support
3. Tree-sitter parsing with adapters for TypeScript, Python, and Kotlin
4. Full relationship extraction: imports, inheritance, ownership
5. Manual layer tagging via .rubicon config file
6. All 6 built-in rules: inheritance_flows_downward, no_circular_ownership, no_upward_dependency, no_layer_skipping, single_responsibility, orphan_detection
7. Terminal violation reporting (structured, color-coded)
8. Static Mermaid diagram output

Do NOT build visualization server, LLM classification, or snapshot/diff features yet — those are Phase 2 and 3.
