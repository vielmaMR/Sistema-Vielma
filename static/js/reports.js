// Dibuja los gráficos del reporte con Chart.js a partir del JSON embebido.
(function () {
  var node = document.getElementById('report-data');
  if (!node || typeof Chart === 'undefined') return;
  var data;
  try { data = JSON.parse(node.textContent); } catch (e) { return; }

  var palette = ['#ff6a00', '#3498db', '#2ecc71', '#9b59b6', '#f1c40f',
    '#e74c3c', '#1abc9c', '#e67e22', '#95a5a6', '#34495e'];

  function labelsVals(obj) {
    return { labels: Object.keys(obj), values: Object.values(obj) };
  }

  function bar(id, obj, label) {
    var c = document.getElementById(id);
    if (!c) return;
    var d = labelsVals(obj);
    if (!d.labels.length) return;
    new Chart(c, {
      type: 'bar',
      data: { labels: d.labels, datasets: [{ label: label, data: d.values, backgroundColor: palette }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
  }

  function pie(id, obj) {
    var c = document.getElementById(id);
    if (!c) return;
    var d = labelsVals(obj);
    if (!d.labels.length) return;
    new Chart(c, {
      type: 'doughnut',
      data: { labels: d.labels, datasets: [{ data: d.values, backgroundColor: palette }] },
      options: { plugins: { legend: { position: 'bottom' } } }
    });
  }

  function line(id, obj) {
    var c = document.getElementById(id);
    if (!c) return;
    var d = labelsVals(obj);
    if (!d.labels.length) return;
    new Chart(c, {
      type: 'line',
      data: { labels: d.labels, datasets: [{ label: 'Órdenes', data: d.values, borderColor: '#ff6a00', backgroundColor: 'rgba(255,106,0,.2)', fill: true, tension: .3 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
  }

  bar('chartWork', data.work, 'Trabajos');
  bar('chartBrand', data.brand, 'Marcas');
  pie('chartVehicle', data.vehicle);
  line('chartDaily', data.daily);
})();
