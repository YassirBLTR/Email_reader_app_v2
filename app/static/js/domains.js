// Domains Management Page JS

class DomainsPage {
  constructor() {
    // Ensure token exists
    const token = localStorage.getItem('token');
    if (!token) {
      window.location.href = '/login';
      return;
    }
    this.init();
  }

  init() {
    this.bindEvents();
    this.loadUser();
    this.loadDomainsList();
  }

  bindEvents() {
    // Navbar logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => this.logout());
    }

    // Open add domain modal
    const openAdd = document.getElementById('openAddDomain');
    if (openAdd) {
      openAdd.addEventListener('click', (e) => {
        e.preventDefault();
        this.openAddDomainModal();
      });
    }

    // Add domain submit
    const addDomainSubmit = document.getElementById('addDomainSubmit');
    if (addDomainSubmit) {
      addDomainSubmit.addEventListener('click', () => this.submitAddDomain());
    }

    // Enter key in domain input
    const domainInput = document.getElementById('domainNameInput');
    if (domainInput) {
      domainInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.submitAddDomain();
        }
      });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refreshDomainsBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.loadDomainsList();
      });
    }
  }

  // API helper with auth and 401 handling
  apiFetch(url, options = {}) {
    const token = localStorage.getItem('token');
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(url, { ...options, headers }).then(res => {
      if (res.status === 401) {
        try { localStorage.removeItem('token'); } catch {}
        window.location.href = '/login';
        throw new Error('Unauthorized');
      }
      return res;
    });
  }

  async loadUser() {
    try {
      const res = await this.apiFetch('/api/auth/me');
      if (!res.ok) return;
      const user = await res.json();
      // Only admins should be here; redirect otherwise
      if (user.role !== 'admin') {
        window.location.href = '/';
        return;
      }
      // Populate navbar dropdown
      const dd = document.getElementById('userDropdown');
      const info = document.getElementById('userInfo');
      const role = document.getElementById('userRole');
      if (dd && info && role) {
        info.textContent = user.username || 'User';
        role.textContent = `Role: Admin`;
        dd.style.display = '';
      }
    } catch (_) {
      // handled by apiFetch
    }
  }

  async logout() {
    try { await this.apiFetch('/api/auth/logout', { method: 'POST' }); } catch {}
    try { localStorage.removeItem('token'); } catch {}
    window.location.href = '/login';
  }

  validateDomain(domain) {
    const re = /^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}$/;
    return re.test(domain);
  }

  openAddDomainModal() {
    const errorBox = document.getElementById('addDomainError');
    const input = document.getElementById('domainNameInput');
    if (errorBox) { errorBox.textContent = ''; errorBox.classList.add('d-none'); }
    if (input) { input.value = ''; input.focus(); }
    const modalEl = document.getElementById('addDomainModal');
    if (modalEl) {
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    }
  }

  async submitAddDomain() {
    const input = document.getElementById('domainNameInput');
    const errorBox = document.getElementById('addDomainError');
    const domain = (input && input.value ? input.value : '').trim().toLowerCase();
    if (!domain) {
      if (errorBox) { errorBox.textContent = 'Domain is required'; errorBox.classList.remove('d-none'); }
      return;
    }
    if (!this.validateDomain(domain)) {
      if (errorBox) { errorBox.textContent = 'Invalid domain name. Example: example.com'; errorBox.classList.remove('d-none'); }
      return;
    }

    try {
      const res = await this.apiFetch('/api/admin/domains', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain })
      });
      if (!res.ok) {
        let detail = 'Failed to add domain';
        try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch {}
        throw new Error(detail);
      }
      // Hide modal
      const modalEl = document.getElementById('addDomainModal');
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      this.showToast('Domain added successfully', 'success');
      this.loadDomainsList();
    } catch (err) {
      if (errorBox) { errorBox.textContent = (err && err.message) ? err.message : 'Failed to add domain'; errorBox.classList.remove('d-none'); }
    }
  }

  async loadDomainsList() {
    const alertBox = document.getElementById('domainsAlert');
    if (alertBox) { alertBox.classList.add('d-none'); alertBox.textContent = ''; }
    try {
      const res = await this.apiFetch('/api/admin/domains');
      if (!res.ok) throw new Error('Failed to load domains');
      const data = await res.json();
      this.renderDomainsTable(data.domains || []);
    } catch (err) {
      if (alertBox) { alertBox.textContent = (err && err.message) ? err.message : 'Failed to load domains'; alertBox.classList.remove('d-none'); }
    }
  }

  renderDomainsTable(items) {
    const tbody = document.querySelector('#domainsTable tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!items.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="3" class="text-center text-muted">No domains found</td>`;
      tbody.appendChild(tr);
      return;
    }
    items.forEach(item => {
      const tr = document.createElement('tr');
      const dateText = item.added_at ? this.formatDateTime(item.added_at) : '-';
      tr.innerHTML = `
        <td>${this.escapeHtml(dateText)}</td>
        <td>${this.escapeHtml(item.domain)}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary me-2" data-action="edit" data-domain="${item.domain}">
            <i class="fas fa-edit"></i> Edit
          </button>
          <button class="btn btn-sm btn-outline-danger" data-action="delete" data-domain="${item.domain}">
            <i class="fas fa-trash"></i> Delete
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
    // Bind actions
    tbody.querySelectorAll('button[data-action]')
      .forEach(btn => btn.addEventListener('click', (e) => {
        const action = e.currentTarget.getAttribute('data-action');
        const domain = e.currentTarget.getAttribute('data-domain');
        if (action === 'delete') this.deleteDomain(domain);
        if (action === 'edit') this.editDomain(domain);
      }));
  }

  async deleteDomain(domain) {
    if (!domain) return;
    if (!confirm(`Delete domain "${domain}"?`)) return;
    const alertBox = document.getElementById('domainsAlert');
    if (alertBox) { alertBox.classList.add('d-none'); alertBox.textContent = ''; }
    try {
      const res = await this.apiFetch(`/api/admin/domains/${encodeURIComponent(domain)}`, { method: 'DELETE' });
      if (!res.ok) {
        let detail = 'Failed to delete domain';
        try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch {}
        throw new Error(detail);
      }
      this.showToast('Domain deleted', 'success');
      this.loadDomainsList();
    } catch (err) {
      if (alertBox) { alertBox.textContent = (err && err.message) ? err.message : 'Failed to delete domain'; alertBox.classList.remove('d-none'); }
    }
  }

  async editDomain(domain) {
    if (!domain) return;
    const newDomain = prompt('Update domain to:', domain);
    if (newDomain === null) return; // cancelled
    const nd = newDomain.trim().toLowerCase();
    if (!nd) { this.showToast('Domain cannot be empty', 'error'); return; }
    if (!this.validateDomain(nd)) { this.showToast('Invalid domain name', 'error'); return; }
    const alertBox = document.getElementById('domainsAlert');
    if (alertBox) { alertBox.classList.add('d-none'); alertBox.textContent = ''; }
    try {
      const res = await this.apiFetch(`/api/admin/domains/${encodeURIComponent(domain)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_domain: nd })
      });
      if (!res.ok) {
        let detail = 'Failed to update domain';
        try { const j = await res.json(); if (j && j.detail) detail = j.detail; } catch {}
        throw new Error(detail);
      }
      this.showToast('Domain updated', 'success');
      this.loadDomainsList();
    } catch (err) {
      if (alertBox) { alertBox.textContent = (err && err.message) ? err.message : 'Failed to update domain'; alertBox.classList.remove('d-none'); }
    }
  }

  // Helpers
  formatDateTime(isoStr) {
    try {
      const d = new Date(isoStr);
      if (!isNaN(d)) return d.toLocaleString();
    } catch {}
    return isoStr;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showToast(message, type) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    container.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => {
      container.removeChild(toast);
    });
  }
}

// Bootstrap page
const domainsPage = new DomainsPage();
