# Design: Rust Counter Application with AIroom UI

## Intent
Build a zero-dependency Rust counter application that embeds a visual AIroom UI dashboard, proving that AI tools like Graphify and Superpowers can be fully contained under `airoom/artifacts/` without polluting the project root.

## Architecture
- **Core Library**: `src/lib.rs` implements a thread-safe `Counter` with history tracking.
- **HTTP Server**: `src/main.rs` binds `127.0.0.1:8080` via `std::net::TcpListener`.
- **Frontend Dashboard**:
  - Counter controls (increment, decrement, reset, live state fetch).
  - AIroom UI panel rendering `airoom/registry.yaml` and active artifact paths.
- **AIroom Containment**:
  - Graphify writes to `airoom/artifacts/graphify-out/`.
  - Superpowers specs, plans, brainstorming, and SDD workspaces reside in `airoom/artifacts/`.
