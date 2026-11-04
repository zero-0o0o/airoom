/**
 * AiroomUI Component for airoom-react-counter.
 */
function createAiroomUI(registryData) {
  return {
    render() {
      const artifacts = registryData.artifacts || {};
      const tools = registryData.tools || {};
      const artifactEntries = Object.entries(artifacts);
      const toolEntries = Object.entries(tools);

      return `
        <div class="airoom-card">
          <div class="header-with-badge">
            <h2>AIroom Dashboard</h2>
            <span class="status-badge">Project Root Clean</span>
          </div>
          <p class="desc">
            All AI-generated artifacts are routed and managed inside <code>airoom/artifacts/</code>.
          </p>

          <div class="section-block">
            <h3>Registered Artifacts (${artifactEntries.length})</h3>
            <div class="artifacts-grid">
              ${artifactEntries.map(([id, entry]) => `
                <div class="artifact-card">
                  <div class="art-title"><strong>${id}</strong></div>
                  <div class="art-path"><code>${entry.path}</code></div>
                  <div class="art-meta">
                    <span class="mode-badge ${entry.management}">${entry.management}</span>
                    <span class="type-tag">${entry.type}</span>
                    <span class="owner-tag">owner: ${entry.owner}</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="section-block">
            <h3>Configured Tools (${toolEntries.length})</h3>
            <div class="tools-list">
              ${toolEntries.map(([id, tool]) => `
                <div class="tool-item">
                  <span class="tool-name">${tool.name}</span>
                  <span class="tool-status">${tool.status}</span>
                  <span class="tool-env">${tool.output_env || tool.output_path || ''}</span>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="boundary-callout">
            <strong>Non-Interference Invariant:</strong> AIroom only manages the <code>airoom/</code> folder and AI tool outputs. It never interferes with application source code, package configurations, or dependencies.
          </div>
        </div>
      `;
    }
  };
}

module.exports = { createAiroomUI };
