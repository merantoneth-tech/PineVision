/**
 * pvCache — sessionStorage caching with TTL for Firestore slow-changing data.
 *
 * Keys are prefixed with 'pv_' to avoid collisions with other sessionStorage use.
 * Default TTL: 60 seconds (appropriate for collections like blocks, operators).
 */

'use strict';

(function () {

    const PREFIX = 'pv_';

    const cache = {

        get(key) {
            try {
                const raw = sessionStorage.getItem(PREFIX + key);
                if (!raw) return null;
                const entry = JSON.parse(raw);
                if (Date.now() > entry.expiry) {
                    sessionStorage.removeItem(PREFIX + key);
                    return null;
                }
                return entry.value;
            } catch (_) {
                return null;
            }
        },

        set(key, value, ttlMs = 60_000) {
            try {
                sessionStorage.setItem(PREFIX + key, JSON.stringify({
                    value,
                    expiry: Date.now() + ttlMs,
                }));
            } catch (_) {
                // sessionStorage full or unavailable — degrade gracefully
            }
        },

        invalidate(key) {
            try {
                sessionStorage.removeItem(PREFIX + key);
            } catch (_) {}
        },

        invalidateAll() {
            try {
                Object.keys(sessionStorage)
                    .filter(k => k.startsWith(PREFIX))
                    .forEach(k => sessionStorage.removeItem(k));
            } catch (_) {}
        },
    };

    window.pvCache = cache;

})();
