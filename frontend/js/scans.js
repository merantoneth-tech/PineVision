/**
 * Scans Page - Real-time Firebase Data Integration
 * Fetches scan history from Firestore scans collection
 */

'use strict';

(function () {

    // ═══════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════

    let scansData = [];
    let currentUserId = null;

    // ═══════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════

    window.initPage = async function () {
        console.log('🚀 Initializing Scans Page...');

        // Check Firebase auth
        const currentUser = auth.getCurrentUser();
        if (!currentUser) {
            console.warn('⚠️ No user logged in');
            window.location.href = '/index.html';
            return;
        }

        currentUserId = currentUser.uid;
        await loadScansData();
    };

    // ═══════════════════════════════════════════════════════════
    // LOAD DATA FROM FIRESTORE
    // ═══════════════════════════════════════════════════════════

    async function loadScansData() {
        try {
            console.log('📊 Loading scans data from Firestore...');
            utils.showLoading('scan-list');

            // First, fetch this user's blocks to create a mapping
            const blocksSnapshot = await firebase.firestore()
                .collection('blocks')
                .where('userId', '==', currentUserId)
                .get();

            // Create a map of blockId to block number
            const blockIdToNumber = {};
            let blockIndex = 1;
            blocksSnapshot.forEach((doc) => {
                blockIdToNumber[doc.id] = blockIndex;
                console.log(`Block mapping: ${doc.id} -> Block ${blockIndex}`);
                blockIndex++;
            });

            console.log('All block IDs:', Object.keys(blockIdToNumber));

            // Fetch only this user's scans, ordered by startTime descending (newest first)
            const scansSnapshot = await firebase.firestore()
                .collection('scans')
                .where('userId', '==', currentUserId)
                .orderBy('startTime', 'desc')
                .get();

            scansData = [];

            for (const doc of scansSnapshot.docs) {
                const data = doc.data();

                console.log(`Scan blockId: "${data.blockId}"`);
                console.log(`Is in mapping? ${!!blockIdToNumber[data.blockId]}`);

                // Get block name using the mapping
                let blockName = 'Unknown Block';
                if (data.blockId && blockIdToNumber[data.blockId]) {
                    blockName = `Block ${blockIdToNumber[data.blockId]}`;
                }

                console.log(`Final blockName: ${blockName}`);

                // Get user name if userId exists
                let operatorName = 'Unknown Operator';
                if (data.userId) {
                    try {
                        const userDoc = await firebase.firestore()
                            .collection('users')
                            .doc(data.userId)
                            .get();
                        if (userDoc.exists) {
                            operatorName = userDoc.data().fullName || userDoc.data().displayName || 'User';
                        }
                    } catch (err) {
                        console.warn('Could not fetch user name:', err);
                    }
                }

                // Calculate duration
                let duration = 'N/A';
                if (data.startTime && data.endTime) {
                    const start = data.startTime.toDate();
                    const end = data.endTime.toDate();
                    const diffMs = end - start;
                    const hours = Math.floor(diffMs / 3600000);
                    const minutes = Math.floor((diffMs % 3600000) / 60000);
                    duration = `${hours}h ${minutes}m`;
                }

                // Parse date
                const scanDate = data.startTime ? data.startTime.toDate() : new Date();
                const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
                const weekNumber = Math.ceil(scanDate.getDate() / 7);

                scansData.push({
                    id: doc.id,
                    day: scanDate.getDate().toString().padStart(2, '0'),
                    month: months[scanDate.getMonth()],
                    year: scanDate.getFullYear().toString(),
                    title: `Weekly Farm Scan - Week ${weekNumber}`,
                    bearing: data.bearing || 0,
                    nonBearing: data.nonBearing || 0,
                    nonViable: data.nonViable || 0,
                    total: data.total || 0,
                    operator: operatorName,
                    drone: 'DJI Mavic 3 Multispectral',
                    time: scanDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
                    duration: duration,
                    status: data.status || 'completed',
                    blockId: data.blockId,
                    blockName: blockName
                });
            }

            console.log(`✅ Loaded ${scansData.length} scans from Firestore`);

            // Render page
            renderScanMetrics();
            renderScanList();

        } catch (error) {
            console.error('❌ Error loading scans data:', error);
            utils.showToast('Failed to load scans data', 'error');
        }
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER SCAN METRICS
    // ═══════════════════════════════════════════════════════════

    function renderScanMetrics() {
        if (scansData.length === 0) {
            document.getElementById('scan-metrics').innerHTML = `
                <div class="col-12">
                    <p style="color: var(--muted); text-align: center;">No scans yet</p>
                </div>
            `;
            return;
        }

        const latest = scansData[0]; // Already sorted by newest first
        const latestDate = `${latest.day} ${latest.month} ${latest.year}`;

        // Calculate percentages
        const bearingPercent = latest.total > 0 ? (latest.bearing / latest.total) * 100 : 0;
        const nonBearingPercent = latest.total > 0 ? (latest.nonBearing / latest.total) * 100 : 0;
        const nonViablePercent = latest.total > 0 ? (latest.nonViable / latest.total) * 100 : 0;

        const metricsHTML = `
            ${buildMetricCard(
            'Total Sessions',
            scansData.length,
            'All drone operations',
            ''
        )}
            ${buildMetricCard(
            'Latest Bearing',
            formatPercent(bearingPercent),
            latestDate,
            'green'
        )}
            ${buildMetricCard(
            'Latest Non-Bearing',
            formatPercent(nonBearingPercent),
            latestDate,
            'amber'
        )}
            ${buildMetricCard(
            'Latest Non-Viable',
            formatPercent(nonViablePercent),
            'Discoloration detected',
            'yellow'
        )}
        `;

        document.getElementById('scan-metrics').innerHTML = metricsHTML;
    }

    // ═══════════════════════════════════════════════════════════
    // RENDER SCAN LIST
    // ═══════════════════════════════════════════════════════════

    function renderScanList() {
        const listEl = document.getElementById('scan-list');

        if (scansData.length === 0) {
            listEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📋</div>
                    <div class="empty-state-title">No scans recorded</div>
                    <div class="empty-state-text">Drone scan sessions will appear here after operations are logged.</div>
                </div>
            `;
            return;
        }

        listEl.innerHTML = scansData.map(buildScanEntry).join('');
    }

    function buildScanEntry(scan) {
        // Calculate percentages from raw counts
        const bearingPercent = scan.total > 0 ? (scan.bearing / scan.total) * 100 : 0;
        const nonBearingPercent = scan.total > 0 ? (scan.nonBearing / scan.total) * 100 : 0;
        const nonViablePercent = scan.total > 0 ? (scan.nonViable / scan.total) * 100 : 0;

        return `
        <div class="scan-entry">
            <div class="sdate">
                <div class="sdate-day">${scan.day}</div>
                <div class="sdate-month">${scan.month}</div>
                <div class="sdate-year">${scan.year}</div>
            </div>
            <div class="sinfo">
                <div class="sinfo-title">${scan.title}</div>
                <div class="spills">
                    <span class="badge good">
                        <span class="bdot"></span>
                        Bearing: <span class="spill-value">${formatPercent(bearingPercent)}</span>
                    </span>
                    <span class="badge warn">
                        <span class="bdot"></span>
                        Non-bearing: <span class="spill-value">${formatPercent(nonBearingPercent)}</span>
                    </span>
                    <span class="badge yellow">
                        <span class="bdot"></span>
                        Non-Viable: <span class="spill-value">${formatPercent(nonViablePercent)}</span>
                    </span>
                </div>
                <div class="sstats">
                    <span>Plants: <strong>${formatNumber(scan.total)}</strong></span>
                    <span>Operator: ${scan.operator}</span>
                    <span>Drone: ${scan.drone}</span>
                    <span>Start: <strong>${scan.time}</strong></span>
                    <span>Duration: <strong>${scan.duration}</strong></span>
                    <span>Blocks: <strong>${scan.blockName || 'undefined'}</strong></span>
                </div>
            </div>
        </div>
    `;
    }

    // ═══════════════════════════════════════════════════════════
    // HELPER FUNCTIONS
    // ═══════════════════════════════════════════════════════════

    function buildMetricCard(title, value, subtitle, colorClass) {
        const colorSuffix = colorClass ? `mc-${colorClass}` : '';
        return `
        <div class="col">
            <div class="mcard ${colorSuffix}">
                <div class="mc-label">${title}</div>
                <div class="mc-val">${value}</div>
                <div class="mc-sub">${subtitle}</div>
            </div>
        </div>
    `;
    }

    function formatPercent(num) {
        return num.toFixed(1) + '%';
    }

    function formatNumber(num) {
        return num.toLocaleString();
    }

})();

