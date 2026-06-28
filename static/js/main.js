// ══════════════════════════════════════════════════════
// КТЗ — main.js
// ══════════════════════════════════════════════════════

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('overlay');
  if (!sidebar) return;
  sidebar.classList.toggle('open');
  overlay && overlay.classList.toggle('show');
}

// Auto-close flash after 5s
document.querySelectorAll('.flash').forEach(f => {
  setTimeout(() => f.remove(), 5000);
});

// Confirm dangerous actions
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// Active nav highlight by exact path
(function () {
  const path = location.pathname;
  document.querySelectorAll('.nav-item').forEach(a => {
    const href = a.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) a.classList.add('active');
  });
})();
