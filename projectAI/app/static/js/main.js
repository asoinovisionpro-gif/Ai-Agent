(function () {
  'use strict';

  const STATUS_CLASSES = ['seat-available', 'seat-reserved', 'seat-occupied', 'seat-faulty'];

  function updateSeat(seatId, newStatus) {
    const el = document.getElementById('seat-' + seatId);
    if (!el) return;

    const oldStatus = el.dataset.status;
    if (oldStatus === newStatus) return;

    el.dataset.status = newStatus;
    STATUS_CLASSES.forEach(c => el.classList.remove(c));
    el.classList.add('seat-' + newStatus);

    el.style.transform = 'scale(1.15)';
    setTimeout(() => { el.style.transform = ''; }, 300);

    if (newStatus === 'available') {
      el.style.cursor = 'pointer';
      el.onclick = function () {
        if (typeof selectSeat === 'function') {
          selectSeat(seatId, el.dataset.seatNumber);
        }
      };
    } else {
      el.style.cursor = 'not-allowed';
      el.onclick = null;
    }
  }

  function initSocketIO() {
    const mapContainers = document.querySelectorAll('[data-lab-id]');
    if (!mapContainers.length) return;
    if (typeof io === 'undefined') return;

    const socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', function () {
      mapContainers.forEach(function (container) {
        const labId = container.dataset.labId;
        if (labId) {
          socket.emit('join', { room: 'lab_' + labId });
        }
      });
    });

    socket.on('seat_state_changed', function (data) {
      updateSeat(data.seat_id, data.new_status);
      updateOccupancyCounter(data.lab_id, data.old_status, data.new_status);
    });

    socket.on('disconnect', function () {
      console.warn('AIDLMS: SocketIO disconnected, seat map may be stale.');
    });
  }

  function updateOccupancyCounter(labId, oldStatus, newStatus) {
    const counters = document.querySelectorAll('[data-occ-lab="' + labId + '"]');
    counters.forEach(function (el) {
      const type = el.dataset.occType;
      const current = parseInt(el.textContent, 10) || 0;
      if (type === oldStatus && current > 0) el.textContent = current - 1;
      if (type === newStatus) el.textContent = current + 1;
    });
  }

  function initAlertAutoDismiss() {
    const container = document.getElementById('alertContainer');
    if (!container) return;
    setTimeout(function () {
      Array.from(container.children).forEach(function (alert) {
        alert.style.transition = 'opacity 0.4s ease';
        alert.style.opacity = '0';
        setTimeout(function () { alert.remove(); }, 400);
      });
    }, 5000);
  }

  function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const menuBtn = document.getElementById('menuBtn');

    if (!sidebar) return;

    function isMobile() { return window.innerWidth < 769; }

    function checkMobile() {
      if (menuBtn) menuBtn.style.display = isMobile() ? 'flex' : 'none';
    }

    window.toggleSidebar = function () {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('visible');
    };

    window.closeSidebar = function () {
      sidebar.classList.remove('open');
      if (overlay) overlay.classList.remove('visible');
    };

    window.addEventListener('resize', checkMobile);
    checkMobile();
  }

  function initModals() {
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      document.querySelectorAll('.modal-backdrop:not(.hidden)').forEach(function (m) {
        m.classList.add('hidden');
      });
    });

    document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
      backdrop.addEventListener('click', function (e) {
        if (e.target === backdrop) backdrop.classList.add('hidden');
      });
    });
  }

  function initFormValidation() {
    document.querySelectorAll('form').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        const btn = form.querySelector('[type="submit"]');
        if (!btn) return;
        if (form.checkValidity()) {
          btn.disabled = true;
          const original = btn.innerHTML;
          btn.innerHTML = '<span class="spinner"></span>';
          setTimeout(function () {
            btn.disabled = false;
            btn.innerHTML = original;
          }, 8000);
        }
      });
    });
  }

  function initDatetimeDefaults() {
    const now = new Date();
    const pad = function (n) { return String(n).padStart(2, '0'); };
    const fmt = function (d) {
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
        'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    };

    document.querySelectorAll('input[type="datetime-local"]').forEach(function (input) {
      if (!input.value && !input.dataset.noDefault) {
        input.min = fmt(now);
      }
    });
  }

  function initTooltips() {
    document.querySelectorAll('[title]').forEach(function (el) {
      el.setAttribute('data-tooltip', el.getAttribute('title'));
    });
  }

  function initOccupancyBars() {
    document.querySelectorAll('.occupancy-bar .fill').forEach(function (bar) {
      const target = bar.style.width;
      bar.style.width = '0';
      requestAnimationFrame(function () {
        setTimeout(function () {
          bar.style.transition = 'width 0.6s ease';
          bar.style.width = target;
        }, 100);
      });
    });
  }

  function initStatCounters() {
    document.querySelectorAll('.stat-value').forEach(function (el) {
      const raw = el.textContent.trim();
      const num = parseFloat(raw.replace('%', ''));
      if (isNaN(num) || num === 0) return;

      const isPercent = raw.includes('%');
      const duration = 800;
      const start = performance.now();

      function tick(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(eased * num);
        el.textContent = current + (isPercent ? '%' : '');
        if (progress < 1) requestAnimationFrame(tick);
      }

      el.textContent = '0' + (isPercent ? '%' : '');
      requestAnimationFrame(tick);
    });
  }

  function initTableSearch() {
    document.querySelectorAll('[data-search-table]').forEach(function (input) {
      const tableId = input.dataset.searchTable;
      const table = document.getElementById(tableId);
      if (!table) return;

      input.addEventListener('input', function () {
        const query = input.value.toLowerCase();
        table.querySelectorAll('tbody tr').forEach(function (row) {
          row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
        });
      });
    });
  }

  function initCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        navigator.clipboard.writeText(btn.dataset.copy).then(function () {
          const orig = btn.textContent;
          btn.textContent = 'Copied!';
          setTimeout(function () { btn.textContent = orig; }, 1500);
        });
      });
    });
  }

  function initTabs() {
    document.querySelectorAll('.tab[data-target]').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = tab.dataset.target;

        tab.closest('.tabs').querySelectorAll('.tab').forEach(function (t) {
          t.classList.remove('active');
        });
        tab.classList.add('active');

        document.querySelectorAll('[data-tab-panel]').forEach(function (panel) {
          panel.style.display = panel.dataset.tabPanel === targetId ? '' : 'none';
        });
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSocketIO();
    initAlertAutoDismiss();
    initSidebar();
    initModals();
    initFormValidation();
    initDatetimeDefaults();
    initTooltips();
    initOccupancyBars();
    initStatCounters();
    initTableSearch();
    initCopyButtons();
    initTabs();
  });

  window.AIDLMS = {
    updateSeat: updateSeat
  };

}());