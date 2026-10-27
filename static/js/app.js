// Registro del service worker para PWA (opcional, no bloquea si falla).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/static/sw.js').catch(function () { /* silencioso */ });
  });
}

// Cronómetros "en curso" en las tarjetas (muestra tiempo desde status_since).
(function () {
  function tick() {
    document.querySelectorAll('[data-live-since]').forEach(function (el) {
      if (el.classList.contains('timer-big')) return; // lo maneja timer.js
      var since = new Date(el.getAttribute('data-live-since'));
      if (isNaN(since)) return;
      var secs = Math.floor((Date.now() - since.getTime()) / 1000);
      // Solo repinta tarjetas de curso con etiqueta corta.
    });
  }
  setInterval(tick, 1000);
})();

// --- Menú lateral desplegable (drawer) ---
(function () {
  var toggle = document.getElementById('menuToggle');
  var drawer = document.getElementById('sideDrawer');
  var overlay = document.getElementById('drawerOverlay');
  var closeBtn = document.getElementById('drawerClose');
  if (!drawer || !overlay) return;

  function open() {
    overlay.hidden = false;
    // Forzar reflow para que la transición de opacidad se aplique.
    void overlay.offsetWidth;
    drawer.classList.add('open');
    overlay.classList.add('show');
    drawer.setAttribute('aria-hidden', 'false');
    if (toggle) { toggle.classList.add('open'); toggle.setAttribute('aria-expanded', 'true'); }
    document.body.style.overflow = 'hidden';
  }

  function close() {
    drawer.classList.remove('open');
    overlay.classList.remove('show');
    drawer.setAttribute('aria-hidden', 'true');
    if (toggle) { toggle.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
    document.body.style.overflow = '';
    // Ocultar el overlay del DOM una vez termina la transición.
    setTimeout(function () { if (!drawer.classList.contains('open')) overlay.hidden = true; }, 280);
  }

  if (toggle) toggle.addEventListener('click', open);
  if (closeBtn) closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && drawer.classList.contains('open')) close();
  });

  // Gesto: deslizar desde el borde izquierdo abre el menú; deslizar a la izquierda lo cierra.
  var startX = null, startY = null, tracking = false;
  var EDGE = 28;       // zona sensible desde el borde izquierdo
  var THRESHOLD = 55;  // distancia mínima para considerar swipe

  window.addEventListener('touchstart', function (e) {
    var t = e.touches[0];
    startX = t.clientX; startY = t.clientY;
    // Solo empezamos a seguir si toca cerca del borde (para abrir) o el menú está abierto (para cerrar).
    tracking = (startX <= EDGE) || drawer.classList.contains('open');
  }, { passive: true });

  window.addEventListener('touchend', function (e) {
    if (!tracking || startX === null) { startX = null; return; }
    var t = e.changedTouches[0];
    var dx = t.clientX - startX;
    var dy = t.clientY - startY;
    // Ignorar si el movimiento fue mayormente vertical.
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > THRESHOLD) {
      if (dx > 0 && !drawer.classList.contains('open')) open();
      else if (dx < 0 && drawer.classList.contains('open')) close();
    }
    startX = null; startY = null; tracking = false;
  }, { passive: true });
})();

// --- Campos de monto: separador de miles mientras se escribe (es-PY) ---
// Muestra "1.500.000" al usuario y envía "1500000" al servidor al hacer submit.
(function () {
  var inputs = document.querySelectorAll('input.money-input');
  if (!inputs.length) return;

  function onlyDigits(s) { return (s || '').replace(/\D/g, ''); }

  function groupThousands(digits) {
    if (!digits) return '';
    // Quita ceros a la izquierda salvo que sea "0".
    digits = digits.replace(/^0+(?=\d)/, '');
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  inputs.forEach(function (inp) {
    // El campo se muestra como texto para permitir los puntos.
    inp.setAttribute('type', 'text');
    inp.setAttribute('inputmode', 'numeric');

    // Formatear el valor inicial (en edición puede venir "1500000" o "1500000.00").
    var initial = onlyDigits(String(inp.value).split('.')[0].split(',')[0]);
    inp.value = groupThousands(initial);

    inp.addEventListener('input', function () {
      var digits = onlyDigits(inp.value);
      inp.value = groupThousands(digits);
    });

    // Al enviar el formulario, dejar solo los dígitos para que el backend valide.
    var form = inp.closest('form');
    if (form && !form._moneyBound) {
      form._moneyBound = true;
      form.addEventListener('submit', function () {
        form.querySelectorAll('input.money-input').forEach(function (m) {
          m.value = onlyDigits(m.value);
        });
      });
    }
  });
})();
