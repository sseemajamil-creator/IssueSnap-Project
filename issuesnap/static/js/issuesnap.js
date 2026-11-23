/**
 * IssueSnap — Main JavaScript
 * AI-Powered Smart Civic Issue Reporting System
 */

'use strict';

/* ============================================================
   Scroll Reveal Animations (IntersectionObserver)
   ============================================================ */
document.addEventListener('DOMContentLoaded', function () {

  // Navbar scroll behaviour
  const navbar = document.querySelector('.navbar-issuesnap');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('scrolled', window.scrollY > 50);
    }, { passive: true });
  }

  // Scroll reveal
  const revealEls = document.querySelectorAll('.reveal, .reveal-left, .reveal-right');
  if (revealEls.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          observer.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -48px 0px' });
    revealEls.forEach(el => observer.observe(el));
  }

  // Animated counters
  const counters = document.querySelectorAll('[data-count]');
  if (counters.length) {
    const countObserver = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          animateCounter(e.target);
          countObserver.unobserve(e.target);
        }
      });
    }, { threshold: 0.5 });
    counters.forEach(c => countObserver.observe(c));
  }

  // Dashboard sidebar toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.querySelector('.sidebar-overlay');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('show');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar?.classList.remove('open');
      overlay.classList.remove('show');
    });
  }

  // Dismiss Django messages as toasts
  const toasts = document.querySelectorAll('.django-toast');
  toasts.forEach(t => {
    setTimeout(() => t.classList.add('hide'), 5000);
  });

  // Notification badge
  loadNotificationCount();

  // Image preview for file inputs
  initImagePreview();

  // AI analysis on image select
  initAIPreview();

  // Tooltips
  initTooltips();

  // Auto-dismiss alerts
  setTimeout(() => {
    document.querySelectorAll('.alert-auto-dismiss').forEach(a => {
      a.style.transition = 'opacity 0.5s';
      a.style.opacity = '0';
      setTimeout(() => a.remove(), 500);
    });
  }, 5000);

});

/* ============================================================
   Counter Animation
   ============================================================ */
function animateCounter(el) {
  const target = parseInt(el.getAttribute('data-count'), 10);
  const duration = 1600;
  const start = performance.now();
  const initial = 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(initial + (target - initial) * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

/* ============================================================
   Image Upload Preview
   ============================================================ */
function initImagePreview() {
  const fileInput = document.getElementById('complaint-images');
  const previewGrid = document.getElementById('image-preview-grid');
  const uploadZone = document.querySelector('.upload-zone');

  if (!fileInput || !previewGrid) return;

  let selectedFiles = [];

  fileInput.addEventListener('change', function () {
    handleFiles(Array.from(this.files));
  });

  if (uploadZone) {
    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      const files = Array.from(e.dataTransfer.files).filter(f =>
        f.type.startsWith('image/')
      );
      handleFiles(files);
    });
  }

  function handleFiles(files) {
    const remaining = 5 - selectedFiles.length;
    const toAdd = files.slice(0, remaining);

    if (files.length > remaining) {
      showToast('You can only upload up to 5 images.', 'warning');
    }

    toAdd.forEach(file => {
      if (file.size > 10 * 1024 * 1024) {
        showToast(`${file.name} exceeds 10MB limit.`, 'error');
        return;
      }
      selectedFiles.push(file);
    });

    updatePreview();
    updateFileInput();
  }

  function updatePreview() {
    previewGrid.innerHTML = '';
    selectedFiles.forEach((file, index) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const item = document.createElement('div');
        item.className = 'image-preview-item';
        item.innerHTML = `
          <img src="${e.target.result}" alt="Preview ${index + 1}">
          <button type="button" class="remove-btn" data-index="${index}" aria-label="Remove image">
            <i class="bi bi-x"></i>
          </button>
          ${index === 0 ? '<span class="badge bg-primary position-absolute bottom-0 start-0 m-1" style="font-size:0.65rem">Primary</span>' : ''}
        `;
        item.querySelector('.remove-btn').addEventListener('click', (ev) => {
          ev.stopPropagation();
          selectedFiles.splice(parseInt(ev.currentTarget.dataset.index), 1);
          updatePreview();
          updateFileInput();
        });
        previewGrid.appendChild(item);
      };
      reader.readAsDataURL(file);
    });

    const countEl = document.getElementById('image-count');
    if (countEl) countEl.textContent = `${selectedFiles.length}/5 images selected`;
  }

  function updateFileInput() {
    const dt = new DataTransfer();
    selectedFiles.forEach(f => dt.items.add(f));
    fileInput.files = dt.files;
  }
}

/* ============================================================
   AI Live Preview (image analysis before submit)
   ============================================================ */
function initAIPreview() {
  const aiPreviewArea = document.getElementById('ai-preview-result');
  if (!aiPreviewArea) return;

  const fileInput = document.getElementById('complaint-images');
  if (!fileInput) return;

  const analyzeBtn = document.getElementById('btn-analyze-ai');
  if (!analyzeBtn) return;

  analyzeBtn.addEventListener('click', async function () {
    if (!fileInput.files || fileInput.files.length === 0) {
      showToast('Please select at least one image first.', 'warning');
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('image', file);

    aiPreviewArea.innerHTML = `
      <div class="ai-loading p-3">
        <div class="ai-pulse"></div>
        <span>Analyzing image with AI...</span>
      </div>
    `;

    try {
      const resp = await fetch('/api/ai/analyze/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: formData,
      });

      const data = await resp.json();

      if (!data.model_available) {
        aiPreviewArea.innerHTML = `
          <div class="alert alert-info">
            <i class="bi bi-info-circle me-2"></i>
            ${data.error || 'AI model not yet available. Your complaint will be reviewed manually.'}
          </div>`;
        return;
      }

      if (data.success) {
        const pct = Math.round(data.confidence * 100);
        const color = pct >= 80 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444';
        aiPreviewArea.innerHTML = `
          <div class="ai-result-card">
            <div class="d-flex align-items-center gap-2 mb-3">
              <i class="bi bi-cpu-fill text-primary fs-5"></i>
              <strong>AI Analysis Result</strong>
              ${data.is_above_threshold
                ? '<span class="badge bg-success ms-auto">High Confidence</span>'
                : '<span class="badge bg-warning ms-auto">Low Confidence</span>'
              }
            </div>
            <div class="mb-3">
              <div class="d-flex justify-content-between mb-1">
                <span class="fw-semibold">${data.display_name || data.predicted_class}</span>
                <span class="fw-bold" style="color:${color}">${pct}%</span>
              </div>
              <div class="ai-confidence-bar">
                <div class="ai-confidence-fill" style="width:${pct}%; background:${color}"></div>
              </div>
            </div>
            <div>
              <small class="text-muted fw-semibold d-block mb-2">Other predictions:</small>
              ${data.top_predictions.slice(1).map(p => `
                <div class="d-flex justify-content-between small text-muted mb-1">
                  <span>${p.display_name || p.class}</span>
                  <span>${Math.round(p.confidence * 100)}%</span>
                </div>
              `).join('')}
            </div>
            <small class="text-muted d-block mt-2">Inference: ${data.inference_time_ms}ms</small>
          </div>
        `;

        // Auto-fill category if confident
        if (data.is_above_threshold) {
          const catSelect = document.getElementById('id_category');
          if (catSelect) {
            for (let opt of catSelect.options) {
              if (opt.text.toLowerCase().includes(data.predicted_class.replace('_', ' '))) {
                catSelect.value = opt.value;
                showToast(`AI suggests category: ${opt.text}`, 'info');
                break;
              }
            }
          }
        }
      } else {
        aiPreviewArea.innerHTML = `
          <div class="alert alert-warning">
            <i class="bi bi-exclamation-triangle me-2"></i>
            ${data.error || 'AI analysis did not return a confident result. Manual review will be performed.'}
          </div>`;
      }
    } catch (err) {
      aiPreviewArea.innerHTML = `
        <div class="alert alert-danger">
          <i class="bi bi-x-circle me-2"></i>
          AI analysis failed. Please proceed with manual submission.
        </div>`;
    }
  });
}

/* ============================================================
   Leaflet Map Initialization (Location Picker)
   ============================================================ */

// Default center: India (centroid of the country)
const DEFAULT_MAP_CENTER = [20.5937, 78.9629];

function initLocationMap(mapId, latInputId, lngInputId, defaultLat, defaultLng) {
  const mapEl = document.getElementById(mapId);
  if (!mapEl || typeof L === 'undefined') {
    // Leaflet not loaded — show a fallback message
    if (mapEl) {
      mapEl.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:#64748B;font-size:0.9rem;text-align:center;padding:1rem">Map could not be loaded. Please check your internet connection.</div>';
    }
    return null;
  }

  const dLat = defaultLat || DEFAULT_MAP_CENTER[0];
  const dLng = defaultLng || DEFAULT_MAP_CENTER[1];

  const map = L.map(mapId, {
    zoomControl: true,
    attributionControl: true,
  }).setView([dLat, dLng], 5);

  // Canonical OSM tile URL — uses referrerPolicy so Referer header is sent
  // and avoids 403 "access blocked" errors per OSM tile usage policy.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
    referrerPolicy: 'no-referrer-when-downgrade',
  }).addTo(map);

  // Fix map rendering if container was hidden then shown (dashboard sidebar)
  setTimeout(() => map.invalidateSize(), 200);

  let marker = null;
  const latInput = document.getElementById(latInputId);
  const lngInput = document.getElementById(lngInputId);

  // ── Reverse geocoding via Nominatim (free, no API key) ──────────
  let geocodeTimer = null;

  function reverseGeocode(lat, lng) {
    const addrDisplay = document.getElementById('reverse-address');
    if (!addrDisplay) return;

    // Debounce to avoid hammering the API on marker drag
    clearTimeout(geocodeTimer);
    geocodeTimer = setTimeout(async () => {
      addrDisplay.innerHTML = '<span class="text-muted"><span class="spinner-border spinner-border-sm me-1"></span>Looking up address...</span>';
      try {
        const resp = await fetch(
          `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
          { headers: { 'Accept-Language': 'en' } }
        );
        if (!resp.ok) throw new Error('Geocoding request failed');
        const data = await resp.json();
        const addr = data.display_name || 'Address not found for this location.';
        addrDisplay.innerHTML = `<i class="bi bi-geo-alt-fill text-primary me-1"></i>${addr}`;

        // Auto-fill the address textarea if it's empty
        const addrField = document.getElementById('id_address');
        if (addrField && !addrField.value.trim()) {
          addrField.value = addr;
        }
      } catch (err) {
        addrDisplay.innerHTML = '<span class="text-muted"><i class="bi bi-geo-alt me-1"></i>Address lookup unavailable. Coordinates saved.</span>';
      }
    }, 500);
  }

  // ── Place / move the marker ──────────────────────────────────────
  function placeMarker(latlng) {
    if (marker) marker.remove();
    marker = L.marker(latlng, { draggable: true }).addTo(map);
    if (latInput) latInput.value = latlng.lat.toFixed(7);
    if (lngInput) lngInput.value = latlng.lng.toFixed(7);
    updateCoordDisplay(latlng.lat, latlng.lng);
    reverseGeocode(latlng.lat, latlng.lng);
    updateLocationStatus(true);

    // Update marker on drag
    marker.on('dragend', function () {
      const pos = marker.getLatLng();
      if (latInput) latInput.value = pos.lat.toFixed(7);
      if (lngInput) lngInput.value = pos.lng.toFixed(7);
      updateCoordDisplay(pos.lat, pos.lng);
      reverseGeocode(pos.lat, pos.lng);
    });
  }

  // ── Click to place marker ────────────────────────────────────────
  map.on('click', (e) => placeMarker(e.latlng));

  // ── "Use My Location" button (browser GPS) ──────────────────────
  const geoBtn = document.getElementById('btn-use-location');
  if (geoBtn) {
    geoBtn.addEventListener('click', () => {
      if (!navigator.geolocation) {
        showToast('Geolocation is not supported by your browser. Please click the map to set location.', 'warning');
        return;
      }
      geoBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Locating...';
      geoBtn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const latlng = L.latLng(pos.coords.latitude, pos.coords.longitude);
          map.setView(latlng, 16);
          placeMarker(latlng);
          geoBtn.innerHTML = '<i class="bi bi-geo-alt-fill me-1"></i>Use My Location';
          geoBtn.disabled = false;
          showToast('Location captured successfully.', 'success');
        },
        (err) => {
          let msg = 'Could not get your location.';
          if (err.code === 1) msg = 'Location permission denied. Please click on the map to set location manually.';
          else if (err.code === 2) msg = 'Location unavailable. Please click on the map to set location.';
          else if (err.code === 3) msg = 'Location request timed out. Please click on the map to set location.';
          showToast(msg, 'warning', 5000);
          geoBtn.innerHTML = '<i class="bi bi-geo-alt-fill me-1"></i>Use My Location';
          geoBtn.disabled = false;
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
      );
    });
  }

  // ── "Clear Location" button ────────────────────────────────────
  const clearBtn = document.getElementById('btn-clear-location');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (marker) { marker.remove(); marker = null; }
      if (latInput) latInput.value = '';
      if (lngInput) lngInput.value = '';
      updateCoordDisplay(null, null);
      const addrDisplay = document.getElementById('reverse-address');
      if (addrDisplay) addrDisplay.innerHTML = '';
      updateLocationStatus(false);
    });
  }

  // If the form already has coordinates (re-render after validation error),
  // restore the marker.
  if (latInput && lngInput && latInput.value && lngInput.value) {
    const lat = parseFloat(latInput.value);
    const lng = parseFloat(lngInput.value);
    if (!isNaN(lat) && !isNaN(lng)) {
      placeMarker(L.latLng(lat, lng));
      map.setView([lat, lng], 15);
    }
  }

  return map;
}

function updateCoordDisplay(lat, lng) {
  const display = document.getElementById('coord-display');
  if (!display) return;
  if (lat === null || lng === null) {
    display.textContent = 'Not set';
    display.classList.remove('text-success');
    display.classList.add('text-danger');
  } else {
    display.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    display.classList.remove('text-danger');
    display.classList.add('text-success');
  }
}

function updateLocationStatus(isSet) {
  const statusEl = document.getElementById('location-status');
  if (!statusEl) return;
  if (isSet) {
    statusEl.innerHTML = '<i class="bi bi-check-circle-fill text-success me-1"></i><span class="text-success fw-600">Location set</span>';
  } else {
    statusEl.innerHTML = '<i class="bi bi-exclamation-circle text-warning me-1"></i><span class="text-warning fw-600">No location selected — click the map</span>';
  }
}

/* ============================================================
   Leaflet Map — Public Issues / Hotspot
   ============================================================ */
function initPublicMap(mapId, complaintsJson) {
  const mapEl = document.getElementById(mapId);
  if (!mapEl || typeof L === 'undefined') return;

  const map = L.map(mapId, { zoomControl: true }).setView([20.5937, 78.9629], 5);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
    referrerPolicy: 'no-referrer-when-downgrade',
  }).addTo(map);
  setTimeout(() => map.invalidateSize(), 300);

  const statusColors = {
    pending: '#F59E0B',
    in_progress: '#2563EB',
    processing: '#8B5CF6',
    resolved: '#10B981',
    completed: '#10B981',
    rejected: '#EF4444',
  };

  if (Array.isArray(complaintsJson)) {
    complaintsJson.forEach(c => {
      if (c.latitude && c.longitude) {
        const color = statusColors[c.status] || '#64748B';
        const marker = L.circleMarker([parseFloat(c.latitude), parseFloat(c.longitude)], {
          radius: 8,
          fillColor: color,
          color: 'white',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.85,
        }).addTo(map);

        marker.bindPopup(`
          <div style="min-width:200px">
            <div class="fw-bold mb-1">${c.title}</div>
            <span class="badge" style="background:${color};color:white;font-size:0.75rem">${c.status.replace('_',' ')}</span>
            <div class="text-muted small mt-1">${c.category__name || 'Uncategorized'}</div>
            <div class="small">${c.district}</div>
          </div>
        `);
      }
    });
  }

  return map;
}

/* ============================================================
   Notifications
   ============================================================ */
async function loadNotificationCount() {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  try {
    const resp = await fetch('/notifications/api/unread-count/');
    const data = await resp.json();
    if (data.count > 0) {
      badge.textContent = data.count > 99 ? '99+' : data.count;
      badge.style.display = 'inline-flex';
    } else {
      badge.style.display = 'none';
    }
  } catch (_) {}
}

/* ============================================================
   Toast Notifications
   ============================================================ */
function showToast(message, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container-custom');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container-custom';
    document.body.appendChild(container);
  }

  const icons = { success: 'check-circle-fill', warning: 'exclamation-triangle-fill', error: 'x-circle-fill', info: 'info-circle-fill' };
  const colors = { success: '#10B981', warning: '#F59E0B', error: '#EF4444', info: '#2563EB' };

  const toast = document.createElement('div');
  toast.className = `toast-custom toast-${type}`;
  toast.style.borderLeftColor = colors[type] || colors.info;
  toast.innerHTML = `
    <i class="bi bi-${icons[type] || icons.info}" style="color:${colors[type]};font-size:1.25rem;flex-shrink:0"></i>
    <div class="flex-1 small">${message}</div>
    <button type="button" onclick="this.closest('.toast-custom').remove()" style="background:none;border:none;cursor:pointer;color:#64748B;padding:0;margin-left:8px">
      <i class="bi bi-x"></i>
    </button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.4s, transform 0.4s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 400);
  }, duration);
}

/* ============================================================
   CSRF Helper
   ============================================================ */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/* ============================================================
   Tooltips
   ============================================================ */
function initTooltips() {
  if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
      new bootstrap.Tooltip(el);
    });
  }
}

/* ============================================================
   Confirm Delete Modals
   ============================================================ */
function confirmDelete(message, formId) {
  if (confirm(message || 'Are you sure you want to delete this item?')) {
    const form = document.getElementById(formId);
    if (form) form.submit();
  }
}

/* ============================================================
   Search with debounce
   ============================================================ */
function debounce(func, wait) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

const searchInput = document.querySelector('[data-live-search]');
if (searchInput) {
  searchInput.addEventListener('input', debounce(function () {
    const form = this.closest('form');
    if (form) form.submit();
  }, 500));
}

/* ============================================================
   Export: make helpers globally available
   ============================================================ */
window.IssueSnap = {
  initLocationMap,
  initPublicMap,
  showToast,
  animateCounter,
  getCookie,
};
