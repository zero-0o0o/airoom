const { Counter } = require('./counter');
const { createCounterApp } = require('./components/CounterApp');
const { createAiroomUI } = require('./components/AiroomUI');

function initializeApp(counterMount, airoomMount, registryData) {
  const counter = new Counter(0, 1);

  function renderAll() {
    if (counterMount) {
      const counterComp = createCounterApp(counter, renderAll);
      counterMount.innerHTML = counterComp.render();
      counterComp.attachEvents(counterMount);
    }
    if (airoomMount) {
      const airoomComp = createAiroomUI(registryData);
      airoomMount.innerHTML = airoomComp.render();
    }
  }

  renderAll();
  return { counter, renderAll };
}

module.exports = { initializeApp };
