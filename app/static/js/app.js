// Email Reader App JavaScript

class EmailReaderApp {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 20;
        this.selectedEmails = new Set();
        this.currentSearchParams = {};
        this.currentUser = null;
        // If no token present, redirect to login early
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/login';
            return;
        }
        this.init();
    }

    init() {
        this.bindEvents();
        // Load authenticated user and update navbar
        this.loadUser();
        this.loadEmailStats();
        this.loadEmails();
    }

    bindEvents() {
        // Search form
        document.getElementById('searchForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.performSearch();
        });

        // Clear filters
        document.getElementById('clearFilters').addEventListener('click', () => {
            this.clearFilters();
        });

        // Select all checkbox
        document.getElementById('selectAllTable').addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });

        // Download selected
        document.getElementById('downloadSelected').addEventListener('click', () => {
            this.showDownloadModal();
        });

        // Download modal confirm
        document.getElementById('confirmDownload').addEventListener('click', () => {
            this.downloadSelectedEmails();
        });

        // Single email download
        document.getElementById('downloadSingleEmail').addEventListener('click', () => {
            this.downloadSingleEmail();
        });

        // Logout
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }

        // Admin Domains button now navigates to /admin/domains (no JS interception needed)

        // Add domain submit
        const addDomainSubmit = document.getElementById('addDomainSubmit');
        if (addDomainSubmit) {
            addDomainSubmit.addEventListener('click', () => this.submitAddDomain());
        }

        // Allow Enter key to submit
        const domainInput = document.getElementById('domainNameInput');
        if (domainInput) {
            domainInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.submitAddDomain();
                }
            });
        }

        // Domains Manager events
        const openAddFromManager = document.getElementById('openAddDomainFromManager');
        if (openAddFromManager) {
            openAddFromManager.addEventListener('click', (e) => {
                e.preventDefault();
                this.openAddDomainModal();
            });
        }
        const refreshDomainsList = document.getElementById('refreshDomainsList');
        if (refreshDomainsList) {
            refreshDomainsList.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadDomainsList();
            });
        }
    }

    // Wrapper around fetch to attach Authorization header and handle 401
    apiFetch(url, options = {}) {
        const token = localStorage.getItem('token');
        const headers = { ...(options.headers || {}) };
        if (token) {
            headers['Authorization'] = 'Bearer ' + token;
        }
        return fetch(url, { credentials: 'same-origin', ...options, headers }).then(res => {
            if (res.status === 401) {
                // Clear invalid token and redirect to login
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
            if (!res.ok) return; // apiFetch will handle 401
            const user = await res.json();
            this.currentUser = user;
            // Update navbar UI
            const userDropdown = document.getElementById('userDropdown');
            const userInfo = document.getElementById('userInfo');
            const userRole = document.getElementById('userRole');
            if (userDropdown && userInfo && userRole) {
                userInfo.textContent = user.username || 'User';
                userRole.textContent = `Role: ${user.role === 'admin' ? 'Admin' : 'User'}`;
                userDropdown.classList.remove('d-none');
            }
            // Admin-only button
            const adminBtn = document.getElementById('adminDomainsBtn');
            if (adminBtn) {
                if (user.role === 'admin') adminBtn.classList.remove('d-none');
                else adminBtn.classList.add('d-none');
            }
        } catch (e) {
            // Handled by apiFetch
        }
    }

    async logout() {
        try {
            // Best-effort server call; stateless
            await this.apiFetch('/api/auth/logout', { method: 'POST' });
        } catch (_) {}
        try { localStorage.removeItem('token'); } catch {}
        window.location.href = '/login';
    }

    // Domain management helpers
    validateDomain(domain) {
        // Must end with standard TLD letters (2-24), no special characters in labels
        const re = /^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}$/;
        return re.test(domain);
    }

    openAddDomainModal() {
        const errorBox = document.getElementById('addDomainError');
        const input = document.getElementById('domainNameInput');
        if (errorBox) {
            errorBox.textContent = '';
            errorBox.classList.add('d-none');
        }
        if (input) {
            input.value = '';
            input.focus();
        }
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
            this.showSuccess('Domain added successfully');
            // Refresh manager list if open
            const managerEl = document.getElementById('domainsManagerModal');
            if (managerEl && managerEl.classList.contains('show')) {
                this.loadDomainsList();
            }
        } catch (err) {
            if (errorBox) { errorBox.textContent = (err && err.message) ? err.message : 'Failed to add domain'; errorBox.classList.remove('d-none'); }
        }
    }

    // Domains manager UI
    openDomainsManager() {
        const modalEl = document.getElementById('domainsManagerModal');
        if (!modalEl) return;
        const modal = new bootstrap.Modal(modalEl);
        this.loadDomainsList().finally(() => modal.show());
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

    formatDateTime(isoStr) {
        try {
            const d = new Date(isoStr);
            if (!isNaN(d)) return d.toLocaleString();
        } catch {}
        return isoStr;
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
            this.showSuccess('Domain deleted');
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
        if (!nd) { this.showError('Domain cannot be empty'); return; }
        if (!this.validateDomain(nd)) { this.showError('Invalid domain name'); return; }
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
            this.showSuccess('Domain updated');
            this.loadDomainsList();
        } catch (err) {
            if (alertBox) { alertBox.textContent = (err && err.message) ? err.message : 'Failed to update domain'; alertBox.classList.remove('d-none'); }
        }
    }

    async loadEmailStats() {
        try {
            const response = await this.apiFetch('/api/emails/stats/summary');
            const stats = await response.json();
            
            document.getElementById('emailStats').innerHTML = `
                <i class="fas fa-envelope me-1"></i>
                ${stats.total_emails} emails
                <i class="fas fa-hdd ms-2 me-1"></i>
                ${this.formatFileSize(stats.total_size_bytes)}
            `;
        } catch (error) {
            console.error('Error loading stats:', error);
            document.getElementById('emailStats').textContent = 'Stats unavailable';
        }
    }

    async loadEmails(page = 1) {
        this.showLoading();
        this.currentPage = page;

        try {
            const url = `/api/emails/?page=${page}&page_size=${this.pageSize}`;
            const response = await this.apiFetch(url);
            const data = await response.json();

            this.renderEmailTable(data);
            this.renderPagination(data);
        } catch (error) {
            console.error('Error loading emails:', error);
            this.showError('Failed to load emails');
        } finally {
            this.hideLoading();
        }
    }

    async performSearch() {
        const searchParams = {
            query: document.getElementById('searchQuery').value.trim(),
            sender: document.getElementById('senderFilter').value.trim(),
            subject: document.getElementById('subjectFilter').value.trim(),
            date_from: document.getElementById('dateFrom').value,
            date_to: document.getElementById('dateTo').value,
            page: 1,
            page_size: this.pageSize
        };

        // Remove empty parameters
        Object.keys(searchParams).forEach(key => {
            if (!searchParams[key]) {
                delete searchParams[key];
            }
        });

        console.log('[Search] Starting search with params:', searchParams);
        this.currentSearchParams = searchParams;
        this.showLoading();

        try {
            const response = await this.apiFetch('/api/emails/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(searchParams)
            });

            if (!response.ok) {
                let errorDetail = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    if (errorData.detail) {
                        if (typeof errorData.detail === 'object') {
                            errorDetail = errorData.detail.message || errorData.detail.error || errorDetail;
                        } else {
                            errorDetail = errorData.detail;
                        }
                    }
                } catch (e) {
                    const errorText = await response.text();
                    if (errorText) errorDetail = errorText;
                }
                throw new Error(errorDetail);
            }

            const data = await response.json();
            console.log('[Search] Received response:', data);
            this.renderEmailTable(data);
            this.renderPagination(data);
        } catch (error) {
            console.error('Error searching emails:', error);
            this.showError(`Failed to search emails: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    clearFilters() {
        document.getElementById('searchForm').reset();
        this.currentSearchParams = {};
        this.loadEmails(1);
    }

    renderEmailTable(data) {
        const tbody = document.getElementById('emailTableBody');
        tbody.innerHTML = '';

        if (data.emails.length === 0) {
            document.getElementById('emailTableContainer').style.display = 'none';
            document.getElementById('noResults').style.display = 'block';
            return;
        }

        document.getElementById('emailTableContainer').style.display = 'block';
        document.getElementById('noResults').style.display = 'none';

        data.emails.forEach(email => {
            const row = this.createEmailRow(email);
            tbody.appendChild(row);
        });

        this.updateDownloadButton();
    }

    createEmailRow(email) {
        const row = document.createElement('tr');
        row.className = 'email-row';
        
        // Format date properly
        const formattedDate = email.date ? new Date(email.date).toLocaleDateString() : 'N/A';
        
        // Truncate long subjects for better display
        const truncatedSubject = email.subject && email.subject.length > 60 
            ? email.subject.substring(0, 60) + '...' 
            : (email.subject || 'No Subject');
        
        // Clean sender display
        const cleanSender = email.sender || 'Unknown';

        row.innerHTML = `
            <td>
                <input type="checkbox" class="email-checkbox" value="${email.filename}" 
                       onchange="app.toggleEmailSelection('${email.filename}', this.checked)">
            </td>
            <td class="email-date">${formattedDate}</td>
            <td class="email-sender" title="${this.escapeHtml(cleanSender)}">${this.escapeHtml(cleanSender.length > 30 ? cleanSender.substring(0, 30) + '...' : cleanSender)}</td>
            <td class="email-subject" title="${this.escapeHtml(email.subject || 'No Subject')}">${this.escapeHtml(truncatedSubject)}</td>
            <td class="email-size">${this.formatFileSize(email.size)}</td>
            <td>
                <button class="btn btn-sm btn-outline-success me-1" onclick="app.downloadSingleEmailDirect('${email.filename}')" title="Download">
                    <i class="fas fa-download"></i>
                </button>
                <button class="btn btn-sm btn-outline-primary" onclick="app.viewEmailDetail('${email.filename}')" title="Open">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;

        return row;
    }

    renderPagination(data) {
        const pagination = document.getElementById('pagination');
        pagination.innerHTML = '';

        if (data.total_pages <= 1) return;

        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${data.page === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#" onclick="app.goToPage(${data.page - 1})">Previous</a>`;
        pagination.appendChild(prevLi);

        // Page numbers
        const startPage = Math.max(1, data.page - 2);
        const endPage = Math.min(data.total_pages, data.page + 2);

        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === data.page ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#" onclick="app.goToPage(${i})">${i}</a>`;
            pagination.appendChild(li);
        }

        // Next button
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${data.page === data.total_pages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#" onclick="app.goToPage(${data.page + 1})">Next</a>`;
        pagination.appendChild(nextLi);
    }

    async goToPage(page) {
        if (Object.keys(this.currentSearchParams).length > 0) {
            this.currentSearchParams.page = page;
            this.performSearch();
        } else {
            this.loadEmails(page);
        }
    }

    toggleEmailSelection(filename, selected) {
        if (selected) {
            this.selectedEmails.add(filename);
        } else {
            this.selectedEmails.delete(filename);
        }
        this.updateDownloadButton();
    }

    toggleSelectAll(selectAll) {
        const checkboxes = document.querySelectorAll('.email-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAll;
            this.toggleEmailSelection(checkbox.value, selectAll);
        });
    }

    updateDownloadButton() {
        const downloadBtn = document.getElementById('downloadSelected');
        downloadBtn.disabled = this.selectedEmails.size === 0;
        downloadBtn.innerHTML = `
            <i class="fas fa-download me-1"></i>
            Download Selected (${this.selectedEmails.size})
        `;
    }

    async viewEmailDetail(filename) {
        try {
            const response = await this.apiFetch(`/api/emails/${encodeURIComponent(filename)}`);
            const email = await response.json();

            this.renderEmailDetail(email);
            const modal = new bootstrap.Modal(document.getElementById('emailDetailModal'));
            modal.show();
        } catch (error) {
            console.error('Error loading email detail:', error);
            this.showError('Failed to load email details');
        }
    }

    renderEmailDetail(email) {
        const content = document.getElementById('emailDetailContent');
        
        const formattedDate = email.date ? new Date(email.date).toLocaleString() : 'N/A';
        const recipients = email.recipients ? email.recipients.join(', ') : 'N/A';
        const cc = email.cc && email.cc.length > 0 ? email.cc.join(', ') : null;
        const bcc = email.bcc && email.bcc.length > 0 ? email.bcc.join(', ') : null;

        let attachmentsHtml = '';
        if (email.attachments && email.attachments.length > 0) {
            attachmentsHtml = `
                <div class="email-detail-section">
                    <div class="email-detail-label">Attachments (${email.attachments.length})</div>
                    <div class="attachment-list">
                        ${email.attachments.map(att => `
                            <div class="attachment-item">
                                <i class="fas fa-paperclip attachment-icon"></i>
                                <span>${att.filename} (${this.formatFileSize(att.size)})</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        // Determine which content to display - prefer HTML body for rich emails
        let emailContent = '';
        if (email.html_body && email.html_body.trim()) {
            emailContent = `
                <div class="email-content-html">
                    <iframe id="emailContentFrame"
                            style="width: 100%; min-height: 400px; border: 1px solid #dee2e6; border-radius: 0.375rem; background: #fff;"
                            sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox">
                    </iframe>
                </div>
            `;
        } else if (email.body && email.body.trim()) {
            emailContent = `
                <div class="email-content-text">
                    <pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">${this.escapeHtml(email.body)}</pre>
                </div>
            `;
        } else {
            emailContent = '<div class="text-muted">No content available</div>';
        }

        content.innerHTML = `
            <div class="email-header-section">
                <div class="row">
                    <div class="col-md-8">
                        <h5 class="email-subject">${this.escapeHtml(email.subject || 'No Subject')}</h5>
                    </div>
                    <div class="col-md-4 text-end">
                        <small class="text-muted">${formattedDate}</small>
                    </div>
                </div>
                <div class="email-meta mt-2">
                    <div><strong>From:</strong> ${this.escapeHtml(email.sender || 'Unknown')}</div>
                    <div><strong>To:</strong> ${this.escapeHtml(recipients)}</div>
                    ${cc ? `<div><strong>CC:</strong> ${this.escapeHtml(cc)}</div>` : ''}
                    ${bcc ? `<div><strong>BCC:</strong> ${this.escapeHtml(bcc)}</div>` : ''}
                </div>
                ${attachmentsHtml}
                <hr>
            </div>
            
            <div class="email-content-section">
                ${emailContent}
            </div>
        `;

        // If we rendered an iframe for HTML content, inject HTML via document.write to avoid srcdoc escaping
        if (email.html_body && email.html_body.trim()) {
            const iframe = document.getElementById('emailContentFrame');
            if (iframe) {
                console.debug('[EmailDetail] html_body length:', email.html_body.length);
                console.debug('[EmailDetail] html_body preview:', email.html_body.slice(0, 120));
                const baseCss = `<style>html,body{margin:0;padding:12px;background:#fff;color:#212529;font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif;} img{max-width:100%;height:auto;} table{max-width:100%;} a{color:#0d6efd;}</style>`;
                const wrapped = `<!doctype html><html><head><meta charset="utf-8"><base target="_blank">${baseCss}</head><body>${email.html_body}</body></html>`;
                try {
                    const doc = iframe.contentWindow && iframe.contentWindow.document;
                    if (doc) {
                        doc.open();
                        doc.write(wrapped);
                        doc.close();
                        // Adjust height after write
                        try {
                            const h = Math.max(400, doc.body.scrollHeight + 20);
                            iframe.style.minHeight = h + 'px';
                        } catch {}
                    }
                } catch (err) {
                    console.error('Iframe write failed:', err);
                }
            }
        }

        // Store current email for download
        this.currentEmailDetail = email;
    }

    showDownloadModal() {
        const modal = new bootstrap.Modal(document.getElementById('downloadModal'));
        modal.show();
    }

    async downloadSelectedEmails() {
        const format = document.querySelector('input[name="downloadFormat"]:checked').value;
        const includeAttachments = document.getElementById('includeAttachments').checked;

        const downloadRequest = {
            filenames: Array.from(this.selectedEmails),
            format: format,
            include_attachments: includeAttachments
        };

        try {
            const response = await this.apiFetch('/api/emails/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(downloadRequest)
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                // Use proper filename based on format
                if (format === 'original') {
                    a.download = 'emails_original.zip';
                } else if (format === 'json') {
                    a.download = 'emails_export.json';
                } else {
                    a.download = 'emails_export.txt';
                }
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('downloadModal'));
                modal.hide();

                this.showSuccess('Download started successfully');
            } else {
                // Try to display server-provided error message
                let detail = '';
                try {
                    const errJson = await response.json();
                    detail = errJson && (errJson.detail || JSON.stringify(errJson));
                } catch (_) {
                    try {
                        detail = await response.text();
                    } catch {}
                }
                console.error('Download failed:', response.status, detail);
                throw new Error(detail || 'Download failed');
            }
        } catch (error) {
            console.error('Error downloading emails:', error);
            this.showError(`Failed to download emails${error && error.message ? ': ' + error.message : ''}`);
        }
    }

    async downloadSingleEmail() {
        if (!this.currentEmailDetail) return;

        const format = 'json'; // Default format for single email
        const downloadRequest = {
            filenames: [this.currentEmailDetail.filename],
            format: format,
            include_attachments: false
        };

        try {
            const response = await this.apiFetch('/api/emails/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(downloadRequest)
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${this.currentEmailDetail.filename}.${format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                this.showSuccess('Download started successfully');
            } else {
                throw new Error('Download failed');
            }
        } catch (error) {
            console.error('Error downloading email:', error);
            this.showError('Failed to download email');
        }
    }

    async downloadSingleEmailDirect(filename) {
        const downloadRequest = {
            filenames: [filename],
            format: 'json',
            include_attachments: false
        };

        try {
            const response = await this.apiFetch('/api/emails/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(downloadRequest)
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.json`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                this.showSuccess('Download started successfully');
            } else {
                throw new Error('Download failed');
            }
        } catch (error) {
            console.error('Error downloading email:', error);
            this.showError('Failed to download email');
        }
    }

    showLoading() {
        document.getElementById('loadingSpinner').style.display = 'block';
        document.getElementById('emailTableContainer').style.display = 'none';
        document.getElementById('noResults').style.display = 'none';
    }

    hideLoading() {
        document.getElementById('loadingSpinner').style.display = 'none';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type) {
        // Create toast container if it doesn't exist
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        // Create toast
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        container.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            container.removeChild(toast);
        });
    }
}

// Initialize the app
const app = new EmailReaderApp();
