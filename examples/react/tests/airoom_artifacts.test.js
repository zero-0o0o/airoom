const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, 'airoom', 'artifacts');

test('AIroom artifacts live under canonical airoom/artifacts directory', () => {
  assert.ok(fs.existsSync(ARTIFACTS_DIR), 'airoom/artifacts must exist');

  // Verify Graphify output location
  const graphifyOut = path.join(ARTIFACTS_DIR, 'graphify-out');
  assert.ok(fs.existsSync(graphifyOut), 'graphify-out must exist under airoom/artifacts/');
  assert.ok(fs.statSync(graphifyOut).isDirectory(), 'graphify-out must be a directory');

  // Verify Superpowers artifacts locations
  const spSpecs = path.join(ARTIFACTS_DIR, 'docs', 'superpowers', 'specs');
  assert.ok(fs.existsSync(spSpecs), 'Superpowers specs must exist under airoom/artifacts/docs/superpowers/specs');

  const spPlans = path.join(ARTIFACTS_DIR, 'docs', 'superpowers', 'plans');
  assert.ok(fs.existsSync(spPlans), 'Superpowers plans must exist under airoom/artifacts/docs/superpowers/plans');

  const spBrainstorm = path.join(ARTIFACTS_DIR, '.superpowers', 'brainstorm');
  assert.ok(fs.existsSync(spBrainstorm), 'Superpowers brainstorm must exist under airoom/artifacts/.superpowers/brainstorm');

  const spSdd = path.join(ARTIFACTS_DIR, '.superpowers', 'sdd');
  assert.ok(fs.existsSync(spSdd), 'Superpowers SDD workspace must exist under airoom/artifacts/.superpowers/sdd');
});

test('Unorganized AI tool defaults are absent from project root', () => {
  assert.ok(!fs.existsSync(path.join(PROJECT_ROOT, 'graphify-out')), 'Root must NOT contain graphify-out');
  assert.ok(!fs.existsSync(path.join(PROJECT_ROOT, 'docs', 'superpowers')), 'Root must NOT contain docs/superpowers');
  assert.ok(!fs.existsSync(path.join(PROJECT_ROOT, '.superpowers')), 'Root must NOT contain .superpowers');
});

test('Registry records all managed artifacts correctly', () => {
  const regPath = path.join(PROJECT_ROOT, 'airoom', 'registry.yaml');
  assert.ok(fs.existsSync(regPath), 'airoom/registry.yaml must exist');

  const content = fs.readFileSync(regPath, 'utf8');
  assert.ok(content.includes('version: 1'), 'Registry must have version: 1');
  assert.ok(content.includes('graphify-output'), 'Registry must record graphify-output');
  assert.ok(content.includes('management: managed'), 'Registry must record management: managed');
  assert.ok(content.includes('superpowers-specs'), 'Registry must record superpowers-specs');
  assert.ok(content.includes('superpowers-plans'), 'Registry must record superpowers-plans');
  assert.ok(content.includes('superpowers-brainstorm'), 'Registry must record superpowers-brainstorm');
  assert.ok(content.includes('superpowers-sdd'), 'Registry must record superpowers-sdd');
});
