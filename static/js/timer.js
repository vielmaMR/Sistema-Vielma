// Cronómetro grande de la orden activa. Se basa en la marca de inicio del
// servidor (data-live-since) más el tiempo base ya acumulado (data-base).
(function () {
  var el = document.querySelector('.timer-big[data-live-since]');
  if (!el) return;
  var since = new Date(el.getAttribute('data-live-since'));
  var base = parseInt(el.getAttribute('data-base') || '0', 10);
  if (isNaN(since)) return;

  function fmt(total) {
    total = Math.max(0, Math.floor(total));
    var h = Math.floor(total / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    function p(n) { return (n < 10 ? '0' : '') + n; }
    if (h > 0) return h + ':' + p(m) + ':' + p(s);
    return p(m) + ':' + p(s);
  }

  // base ya incluye la sesión activa parcial calculada por el servidor al cargar,
  // por lo que medimos el delta desde "ahora de carga".
  var loadStart = Date.now();
  function render() {
    var delta = (Date.now() - loadStart) / 1000;
    el.textContent = fmt(base + delta);
  }
  render();
  setInterval(render, 1000);
})();
