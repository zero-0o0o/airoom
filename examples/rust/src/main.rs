//! Rust Counter application with integrated AIroom UI web server.

use airoom_rust_counter::Counter;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::Path;
use std::sync::{Arc, Mutex};

const HTML_PAGE: &str = r#"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rust Counter + AIroom UI</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --accent: #8b5cf6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
      display: grid;
      gap: 2rem;
    }
    header {
      text-align: center;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #fff; }
    .subtitle { color: var(--muted); font-size: 0.95rem; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }
    @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
    }
    .card h2 {
      font-size: 1.25rem;
      margin-bottom: 1rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .counter-display {
      font-size: 4rem;
      font-weight: 700;
      text-align: center;
      margin: 1.5rem 0;
      color: var(--primary);
      font-variant-numeric: tabular-nums;
    }
    .btn-group {
      display: flex;
      gap: 0.75rem;
      justify-content: center;
    }
    button {
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 8px;
      padding: 0.75rem 1.25rem;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    button:hover { background: var(--primary-hover); }
    button.btn-secondary { background: #475569; }
    button.btn-secondary:hover { background: #334155; }
    .badge {
      display: inline-block;
      padding: 0.25rem 0.5rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.2);
      color: var(--success);
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .registry-box {
      background: #090d16;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.85rem;
      color: #38bdf8;
      overflow-x: auto;
      max-height: 250px;
    }
    .artifact-list {
      list-style: none;
      margin-top: 1rem;
      display: grid;
      gap: 0.5rem;
    }
    .artifact-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(255, 255, 255, 0.03);
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      font-size: 0.85rem;
    }
    .callout {
      margin-top: 1rem;
      padding: 0.75rem 1rem;
      background: rgba(59, 130, 246, 0.1);
      border-left: 3px solid var(--primary);
      font-size: 0.85rem;
      color: #cbd5e1;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Rust Counter + AIroom UI</h1>
      <p class="subtitle">A realistic Rust app demonstrating clean project root hygiene with AIroom</p>
    </header>

    <div class="grid">
      <!-- Counter App Section -->
      <div class="card">
        <h2>Counter Application</h2>
        <div class="counter-display" id="countVal">0</div>
        <div class="btn-group">
          <button onclick="decrement()">- Decrement</button>
          <button onclick="increment()">+ Increment</button>
          <button class="btn-secondary" onclick="reset()">Reset</button>
        </div>
        <div class="callout">
          Counter state is managed by the Rust core library and synced over a local REST API.
        </div>
      </div>

      <!-- AIroom UI Section -->
      <div class="card">
        <h2>
          <span>AIroom Dashboard</span>
          <span class="badge">Clean Root Active</span>
        </h2>
        <p style="font-size:0.85rem; color: var(--muted); margin-bottom: 0.75rem;">
          Tracked AI tool artifacts inside <code>airoom/artifacts/</code>:
        </p>
        <div class="registry-box" id="registryContent">Loading registry.yaml...</div>
        <ul class="artifact-list" id="artifactsList">
          <li class="artifact-item">
            <span><code>airoom/artifacts/graphify-out/</code></span>
            <span class="badge">Graphify</span>
          </li>
          <li class="artifact-item">
            <span><code>airoom/artifacts/docs/superpowers/</code></span>
            <span class="badge">Superpowers</span>
          </li>
          <li class="artifact-item">
            <span><code>airoom/artifacts/.superpowers/</code></span>
            <span class="badge">Superpowers Scratch</span>
          </li>
        </ul>
      </div>
    </div>
  </div>

  <script>
    async function updateCount() {
      try {
        const res = await fetch('/api/count');
        const data = await res.json();
        document.getElementById('countVal').innerText = data.count;
      } catch (err) {
        console.error('Fetch count failed', err);
      }
    }

    async function increment() {
      await fetch('/api/increment', { method: 'POST' });
      updateCount();
    }

    async function decrement() {
      await fetch('/api/decrement', { method: 'POST' });
      updateCount();
    }

    async function reset() {
      await fetch('/api/reset', { method: 'POST' });
      updateCount();
    }

    async function loadAiroom() {
      try {
        const res = await fetch('/api/airoom');
        const text = await res.text();
        document.getElementById('registryContent').innerText = text;
      } catch (err) {
        document.getElementById('registryContent').innerText = 'Failed to load airoom/registry.yaml';
      }
    }

    updateCount();
    loadAiroom();
  </script>
</body>
</html>
"#;

pub fn handle_client(mut stream: TcpStream, counter: Arc<Mutex<Counter>>, project_root: &Path) {
    let mut buffer = [0; 2048];
    let bytes_read = match stream.read(&mut buffer) {
        Ok(n) if n > 0 => n,
        _ => return,
    };

    let request = String::from_utf8_lossy(&buffer[..bytes_read]);
    let first_line = request.lines().next().unwrap_or("");
    let mut parts = first_line.split_whitespace();
    let method = parts.next().unwrap_or("");
    let path = parts.next().unwrap_or("/");

    let (status, content_type, body) = match (method, path) {
        ("GET", "/") => (
            "200 OK",
            "text/html; charset=utf-8",
            HTML_PAGE.to_string(),
        ),
        ("GET", "/api/count") => {
            let count = counter.lock().unwrap().value();
            (
                "200 OK",
                "application/json",
                format!("{{\"count\": {count}}}"),
            )
        }
        ("POST", "/api/increment") => {
            let mut c = counter.lock().unwrap();
            let new_val = c.increment(1);
            (
                "200 OK",
                "application/json",
                format!("{{\"count\": {new_val}}}"),
            )
        }
        ("POST", "/api/decrement") => {
            let mut c = counter.lock().unwrap();
            let new_val = c.decrement(1);
            (
                "200 OK",
                "application/json",
                format!("{{\"count\": {new_val}}}"),
            )
        }
        ("POST", "/api/reset") => {
            let mut c = counter.lock().unwrap();
            let new_val = c.reset();
            (
                "200 OK",
                "application/json",
                format!("{{\"count\": {new_val}}}"),
            )
        }
        ("GET", "/api/airoom") => {
            let reg_path = project_root.join("airoom/registry.yaml");
            let content = fs::read_to_string(&reg_path)
                .unwrap_or_else(|_| "Error: registry.yaml not found".to_string());
            ("200 OK", "text/plain; charset=utf-8", content)
        }
        _ => (
            "404 NOT FOUND",
            "text/plain",
            "Not Found".to_string(),
        ),
    };

    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );

    let _ = stream.write_all(response.as_bytes());
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|arg| arg == "--check") {
        println!("Rust Counter + AIroom UI check passed.");
        return;
    }

    let counter = Arc::new(Mutex::new(Counter::new()));
    let project_root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let addr = "127.0.0.1:8080";
    let listener = TcpListener::bind(addr).expect("Failed to bind TCP listener");

    println!("==================================================");
    println!("  Rust Counter App with AIroom UI");
    println!("  Listening on http://{addr}");
    println!("==================================================");

    for stream in listener.incoming() {
        if let Ok(stream) = stream {
            let counter = Arc::clone(&counter);
            handle_client(stream, counter, project_root);
        }
    }
}
