const test = require('node:test');
const assert = require('node:assert');
const { Counter } = require('../src/counter');

test('Counter initializes with default values', () => {
  const counter = new Counter();
  assert.strictEqual(counter.getValue(), 0);
  assert.strictEqual(counter.getStep(), 1);
  assert.strictEqual(counter.getHistory().length, 1);
});

test('Counter handles custom initial value and step', () => {
  const counter = new Counter(10, 5);
  assert.strictEqual(counter.getValue(), 10);
  assert.strictEqual(counter.getStep(), 5);
});

test('Counter increment and decrement state transitions', () => {
  const counter = new Counter(0, 2);
  counter.increment();
  assert.strictEqual(counter.getValue(), 2);

  counter.increment(3);
  assert.strictEqual(counter.getValue(), 5);

  counter.decrement();
  assert.strictEqual(counter.getValue(), 3);

  const history = counter.getHistory();
  assert.strictEqual(history.length, 4);
  assert.strictEqual(history[history.length - 1].action, 'decrement');
});

test('Counter reset restores state to zero', () => {
  const counter = new Counter(50);
  counter.increment(20);
  assert.strictEqual(counter.getValue(), 70);

  counter.reset();
  assert.strictEqual(counter.getValue(), 0);
});

test('Counter rejects invalid step values', () => {
  const counter = new Counter();
  assert.throws(() => counter.setStep(-1), /positive number/);
  assert.throws(() => counter.setStep('bad'), /positive number/);
});
