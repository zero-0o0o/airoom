---
name: graphify
description: Run Graphify with output routed directly into airoom/artifacts/graphify-out.
---

# Graphify Integration for AIroom

Always set `GRAPHIFY_OUT=airoom/artifacts/graphify-out` before running Graphify commands. This ensures that the generated AST extraction, graph JSON, and reports reside in AIroom's canonical artifacts directory rather than cluttering the project root.

## Usage

```bash
# Build the code knowledge graph
GRAPHIFY_OUT=airoom/artifacts/graphify-out graphify . --code-only --no-viz

# Query the graph
graphify query "<question>" --graph airoom/artifacts/graphify-out/graph.json
```
