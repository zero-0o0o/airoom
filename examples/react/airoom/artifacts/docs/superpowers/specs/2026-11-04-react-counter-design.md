# Design: React Counter Application with AIroom UI

## Intent
Build a modern, zero-dependency Node/React counter application with an integrated AIroom UI panel, demonstrating that web application frontends can isolate AI tool outputs cleanly under `airoom/artifacts/`.

## Architecture
- **Counter State**: `src/counter.js` manages numeric count, step value, and action history.
- **Counter Component**: `src/components/CounterApp.js` provides interactive increment, decrement, and reset controls.
- **AIroom UI Component**: `src/components/AiroomUI.js` displays registry statistics, artifact cards, and boundary invariants.
- **Web Server**: `src/server.js` serves HTML, JavaScript bundles, and registry data.
- **AIroom Tool Integration**:
  - Graphify builds knowledge graph in `airoom/artifacts/graphify-out/`.
  - Superpowers specs, plans, brainstorm, and SDD workspaces are routed to `airoom/artifacts/`.
