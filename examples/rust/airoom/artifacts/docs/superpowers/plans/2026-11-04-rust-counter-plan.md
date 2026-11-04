# Implementation Plan: Rust Counter with AIroom UI

**Spec:** [Rust Counter Design](../specs/2026-11-04-rust-counter-design.md)

## Tasks
1. Implement Counter struct and unit tests in `src/lib.rs`.
2. Implement HTTP server and single-page Counter + AIroom UI in `src/main.rs`.
3. Configure `GRAPHIFY_OUT=airoom/artifacts/graphify-out` and build graph.
4. Route Superpowers specs, plans, and SDD workspace into `airoom/artifacts/`.
5. Register artifacts and tools in `airoom/registry.yaml`.
6. Run `cargo test` to verify logic and artifact isolation.
