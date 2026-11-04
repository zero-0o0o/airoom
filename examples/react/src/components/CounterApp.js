/**
 * CounterApp Component for airoom-react-counter.
 */
function createCounterApp(counterInstance, onStateChange) {
  return {
    render() {
      const val = counterInstance.getValue();
      const step = counterInstance.getStep();
      const history = counterInstance.getHistory();

      return `
        <div class="counter-card">
          <h2>Counter Application</h2>
          <div class="counter-value">${val}</div>
          <div class="step-control">
            <label>Step Size:</label>
            <input type="number" id="stepInput" value="${step}" min="1" max="100" />
          </div>
          <div class="button-row">
            <button id="decBtn" class="btn btn-primary">- Decrement</button>
            <button id="incBtn" class="btn btn-primary">+ Increment</button>
            <button id="resetBtn" class="btn btn-secondary">Reset</button>
          </div>
          <div class="history-section">
            <h3>Recent Activity</h3>
            <ul class="history-list">
              ${history.slice(-5).reverse().map(item => `
                <li>
                  <span class="action-tag">${item.action}</span>
                  <span class="val-tag">Value: ${item.value}</span>
                </li>
              `).join('')}
            </ul>
          </div>
        </div>
      `;
    },
    attachEvents(container) {
      const incBtn = container.querySelector('#incBtn');
      const decBtn = container.querySelector('#decBtn');
      const resetBtn = container.querySelector('#resetBtn');
      const stepInput = container.querySelector('#stepInput');

      if (incBtn) {
        incBtn.onclick = () => {
          counterInstance.increment();
          if (onStateChange) onStateChange();
        };
      }
      if (decBtn) {
        decBtn.onclick = () => {
          counterInstance.decrement();
          if (onStateChange) onStateChange();
        };
      }
      if (resetBtn) {
        resetBtn.onclick = () => {
          counterInstance.reset();
          if (onStateChange) onStateChange();
        };
      }
      if (stepInput) {
        stepInput.onchange = (e) => {
          const val = parseInt(e.target.value, 10);
          if (val > 0) {
            counterInstance.setStep(val);
            if (onStateChange) onStateChange();
          }
        };
      }
    }
  };
}

module.exports = { createCounterApp };
