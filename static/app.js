// TechMatch UI helpers (no external dependencies)

function openModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('is-open');
  // Prevent background scroll
  document.documentElement.classList.add('tm-modal-open');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('is-open');
  document.documentElement.classList.remove('tm-modal-open');
}

function backdropClose(ev, id) {
  // Only close if user clicked the backdrop itself (not inside the modal)
  if (ev && ev.target && ev.target.classList && ev.target.classList.contains('tm-modal-backdrop')) {
    closeModal(id);
  }
}

// Declarative bindings
document.addEventListener('click', (ev) => {
  const openBtn = ev.target.closest('[data-modal-open]');
  if (openBtn) {
    ev.preventDefault();
    openModal(openBtn.getAttribute('data-modal-open'));
    return;
  }

  const closeBtn = ev.target.closest('[data-modal-close]');
  if (closeBtn) {
    ev.preventDefault();
    closeModal(closeBtn.getAttribute('data-modal-close'));
  }
});

// Escape closes any open modal
document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  const open = document.querySelector('.tm-modal-backdrop.is-open');
  if (open && open.id) closeModal(open.id);
});
