/**
 * app.js — Shared JavaScript for Office Tracking Dashboard
 * =========================================================
 * Handles: authentication guards, API fetch wrapper, utility functions.
 * All pages include this via base.html.
 */

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }
    const username = localStorage.getItem('username') || 'Operator';
    const role = localStorage.getItem('role') || 'staff';
    const userEl = document.getElementById('usernameDisplay');
    const roleEl = document.getElementById('userRoleDisplay');
    const avatarEl = document.getElementById('avatarCircle');

    if (userEl) userEl.textContent = username;
    if (roleEl) roleEl.textContent = role.toUpperCase();
    if (avatarEl) avatarEl.textContent = username.substring(0, 2).toUpperCase();
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('username');
    window.location.href = '/login';
}

// ---------------------------------------------------------------------------
// API fetch wrapper — injects Bearer token, handles 401 redirects
// ---------------------------------------------------------------------------

async function apiFetch(url, options = {}) {
    const token = localStorage.getItem('token');
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(options.headers || {}),
    };

    // Don't set Content-Type for FormData (browser sets it with boundary)
    if (options.body instanceof FormData) {
        delete headers['Content-Type'];
    }

    const resp = await fetch(url, { ...options, headers });

    if (resp.status === 401) {
        // Token expired or invalid — redirect to login
        logout();
        throw new Error('Session expired. Please log in again.');
    }

    if (resp.status === 403) {
        throw new Error('Access denied. You do not have permission to view this data.');
    }

    if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
            const err = await resp.json();
            detail = err.detail || detail;
        } catch (_) {}
        throw new Error(detail);
    }

    // Return null for 204 No Content
    if (resp.status === 204) return null;

    return resp.json();
}

// ---------------------------------------------------------------------------
// Formatting utilities
// ---------------------------------------------------------------------------

/**
 * Format an ISO-8601 UTC timestamp as local time string.
 * e.g. "2026-09-08T09:32:11+00:00" → "09:32 AM"
 */
function formatTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    } catch (_) { return isoStr; }
}

/**
 * Format an ISO-8601 timestamp as date + time.
 */
function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleString('en-IN', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch (_) { return isoStr; }
}

/**
 * Escape HTML special chars to prevent XSS when inserting into innerHTML.
 */
function escHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Format minutes as "Xh Ym" (e.g. 90 → "1h 30m").
 */
function formatMinutes(mins) {
    if (!mins && mins !== 0) return '—';
    const h = Math.floor(mins / 60);
    const m = Math.round(mins % 60);
    if (h === 0) return `${m}m`;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
}
