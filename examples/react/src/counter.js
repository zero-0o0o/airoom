/**
 * Core Counter state manager for airoom-react-counter.
 */
class Counter {
  constructor(initialValue = 0, step = 1) {
    this.value = initialValue;
    this.step = step;
    this.history = [
      { action: 'init', value: initialValue, timestamp: Date.now() },
    ];
  }

  getValue() {
    return this.value;
  }

  getStep() {
    return this.step;
  }

  getHistory() {
    return [...this.history];
  }

  setStep(newStep) {
    if (typeof newStep !== 'number' || newStep <= 0) {
      throw new Error('Step must be a positive number');
    }
    this.step = newStep;
    return this.step;
  }

  increment(amount = this.step) {
    this.value += amount;
    this.history.push({
      action: 'increment',
      amount,
      value: this.value,
      timestamp: Date.now(),
    });
    return this.value;
  }

  decrement(amount = this.step) {
    this.value -= amount;
    this.history.push({
      action: 'decrement',
      amount,
      value: this.value,
      timestamp: Date.now(),
    });
    return this.value;
  }

  reset() {
    this.value = 0;
    this.history.push({
      action: 'reset',
      value: 0,
      timestamp: Date.now(),
    });
    return this.value;
  }
}

module.exports = { Counter };
