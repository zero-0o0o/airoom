<!-- AIROOM:START -->

# AIroom

AIroom is the shared infrastructure and coordination layer
for AI agents and tools.

To keep the project root clean and maintainable:

1. Read `airoom/AIROOM.md` for navigation, layout, and tool guidelines.
2. Route new AI tool outputs (e.g. Graphify, Superpowers, scratchpads)
   into `airoom/artifacts/` whenever supported.
3. When discovering unorganized AI artifacts in the project root,
   consult `airoom/skills/artifact-discovery/SKILL.md` and
   `airoom/skills/artifact-organization/SKILL.md` to safely relocate them
   or track them as external.
4. Maintain `airoom/registry.yaml` following `airoom/skills/registry-management/SKILL.md`.
5. Strictly adhere to safety boundaries in `airoom/skills/safe-management/SKILL.md`:
   never overwrite files, never delete user data, and never break tools.

All AIroom-managed artifacts must follow the
AIroom registry and management conventions.

<!-- AIROOM:END -->

