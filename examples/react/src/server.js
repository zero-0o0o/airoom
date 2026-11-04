/**
 * Node.js HTTP server for airoom-react-counter.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const PROJECT_ROOT = path.resolve(__dirname, '..');
const PUBLIC_DIR = path.join(PROJECT_ROOT, 'public');

function parseSimpleYaml(content) {
  // Basic parser for demonstration display
  const result = { version: 1, artifacts: {}, tools: {} };
  let section = null;
  let currentKey = null;

  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    if (trimmed.startsWith('artifacts:')) {
      section = 'artifacts';
      continue;
    }
    if (trimmed.startsWith('tools:')) {
      section = 'tools';
      continue;
    }

    if (section && line.startsWith('  ') && !line.startsWith('    ')) {
      currentKey = trimmed.replace(':', '');
      result[section][currentKey] = {};
    } else if (section && currentKey && line.startsWith('    ')) {
      const [k, ...v] = trimmed.split(':');
      if (k && v) {
        result[section][currentKey][k.trim()] = v.join(':').trim();
      }
    }
  }
  return result;
}

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/index.html') {
    const html = fs.readFileSync(path.join(PUBLIC_DIR, 'index.html'), 'utf8');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(html);
  } else if (req.url === '/app.bundle.js') {
    const registryPath = path.join(PROJECT_ROOT, 'airoom', 'registry.yaml');
    let registryData = { artifacts: {}, tools: {} };
    if (fs.existsSync(registryPath)) {
      registryData = parseSimpleYaml(fs.readFileSync(registryPath, 'utf8'));
    }

    const bundleScript = `
      const registryData = ${JSON.stringify(registryData)};
      const counterComp = (${require('./components/CounterApp').createCounterApp.toString()});
      const airoomComp = (${require('./components/AiroomUI').createAiroomUI.toString()});
      const CounterClass = (${require('./counter').Counter.toString()});

      const counter = new CounterClass(0, 1);
      const cMount = document.getElementById('counterRoot');
      const aMount = document.getElementById('airoomRoot');

      function render() {
        if (cMount) {
          const app = counterComp(counter, render);
          cMount.innerHTML = app.render();
          app.attachEvents(cMount);
        }
        if (aMount) {
          aMount.innerHTML = airoomComp(registryData).render();
        }
      }
      render();
    `;
    res.writeHead(200, { 'Content-Type': 'application/javascript' });
    res.end(bundleScript);
  } else if (req.url === '/api/registry') {
    const registryPath = path.join(PROJECT_ROOT, 'airoom', 'registry.yaml');
    const content = fs.existsSync(registryPath) ? fs.readFileSync(registryPath, 'utf8') : '';
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(content);
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
});

if (require.main === module) {
  server.listen(PORT, '127.0.0.1', () => {
    console.log(`React Counter + AIroom UI running on http://127.0.0.1:${PORT}`);
  });
}

module.exports = { server };
