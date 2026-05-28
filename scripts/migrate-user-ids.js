#!/usr/bin/env node
/**
 * migrate-user-ids.js
 *
 * One-time migration: stamp userId on documents in `blocks` and
 * `monitoring_alerts` that are missing the field.
 *
 * OWNERSHIP RESOLUTION
 * --------------------
 *   blocks:
 *     New blocks already have userId (written by blocks.html).
 *     Orphan blocks (no userId, no ownership signal) require
 *     --fallback-owner=<uid>; without it they are reported but skipped.
 *
 *   monitoring_alerts:
 *     Resolved via blockId → blocks/{blockId}.userId chain.
 *     Alerts whose block also lacks userId are skipped and reported.
 *     Run block migration first (with --fallback-owner), then re-run
 *     this script to pick up the newly-assigned alerts.
 *
 * SAFETY GUARANTEES
 * -----------------
 *   - Dry-run by default; --run flag required to write
 *   - Never overwrites an existing userId field
 *   - Processes in 400-op Firestore batches (well under the 500 limit)
 *   - Does NOT touch the scans collection
 *
 * USAGE
 * -----
 *   # 1. Install dependencies (one time only)
 *   cd scripts && npm install
 *
 *   # 2. Inspect — shows what will change, writes nothing
 *   node migrate-user-ids.js
 *
 *   # 3. Execute migration
 *   node migrate-user-ids.js --run
 *
 *   # 4. Execute + assign orphan blocks to a specific owner
 *   node migrate-user-ids.js --run --fallback-owner=<uid>
 *
 * To find a UID: Firebase Console → Authentication → Users (copy the UID column)
 */

'use strict';

const admin = require('firebase-admin');
const path  = require('path');
const fs    = require('fs');

// ─── Configuration ────────────────────────────────────────────────────────────

const SERVICE_ACCOUNT_PATH = path.resolve(
    __dirname, '..', 'backend', 'serviceAccountKey.json'
);

const BATCH_SIZE = 400; // Firestore hard limit is 500; leave headroom

const args          = process.argv.slice(2);
const DRY_RUN       = !args.includes('--run');
const FALLBACK_OWNER = (() => {
    const flag = args.find(a => a.startsWith('--fallback-owner='));
    return flag ? flag.split('=')[1].trim() : null;
})();

// ─── Initialise Firebase Admin ────────────────────────────────────────────────

if (!fs.existsSync(SERVICE_ACCOUNT_PATH)) {
    console.error(`\n❌  Service account key not found at:\n    ${SERVICE_ACCOUNT_PATH}`);
    console.error('\n    Download it from:');
    console.error('    Firebase Console → Project Settings → Service Accounts → Generate new private key\n');
    process.exit(1);
}

admin.initializeApp({ credential: admin.credential.cert(SERVICE_ACCOUNT_PATH) });
const db = admin.firestore();

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function commitBatch(batch, opCount) {
    if (opCount > 0) await batch.commit();
    return { batch: db.batch(), opCount: 0 };
}

function fmtDocId(id) {
    return id.length > 20 ? id.substring(0, 20) + '…' : id;
}

function sampleRow(docId, data, fields) {
    const parts = fields.map(f => {
        const v = data[f];
        const display = v === undefined ? '<missing>'
            : (v && typeof v === 'object' && v._seconds) ? '<Timestamp>'
            : JSON.stringify(v);
        return `${f}: ${display}`;
    });
    return `    [${fmtDocId(docId)}]  ${parts.join('  |  ')}`;
}

// ─── Phase 1: Inspect blocks ─────────────────────────────────────────────────

async function inspectBlocks() {
    console.log('\n━━━  BLOCKS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    const snap = await db.collection('blocks').get();
    const blockOwnerMap = {};
    const orphans       = [];

    snap.forEach(doc => {
        const d = doc.data();
        if (d.userId) {
            blockOwnerMap[doc.id] = d.userId;
        } else {
            orphans.push({ id: doc.id, data: d });
        }
    });

    console.log(`  Total documents : ${snap.size}`);
    console.log(`  Have userId     : ${snap.size - orphans.length}`);
    console.log(`  Missing userId  : ${orphans.length}`);

    if (orphans.length > 0) {
        console.log(`\n  Sample orphan blocks (up to 5 shown):`);
        orphans.slice(0, 5).forEach(({ id, data }) =>
            console.log(sampleRow(id, data, ['blockName', 'section', 'area', 'createdAt']))
        );

        console.log();
        if (FALLBACK_OWNER) {
            console.log(`  ✔  Will assign userId="${FALLBACK_OWNER}" to ${orphans.length} orphan block(s).`);
        } else {
            console.log('  ⚠️  No ownership signal found on these documents.');
            console.log('      They will be SKIPPED unless you supply --fallback-owner=<uid>.');
            console.log('      Hint: open Firebase Console → Authentication → Users to find the UID.');
        }
    }

    return {
        total    : snap.size,
        orphanIds: orphans.map(o => o.id),
        blockOwnerMap,
    };
}

// ─── Phase 1: Inspect monitoring_alerts ──────────────────────────────────────

async function inspectAlerts(blockOwnerMap) {
    console.log('\n━━━  MONITORING_ALERTS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    const snap = await db.collection('monitoring_alerts').get();

    let alreadyTagged = 0;
    let resolvable    = 0;
    let unresolvable  = 0;
    const unresolvableSamples = [];

    snap.forEach(doc => {
        const d = doc.data();
        if (d.userId) {
            alreadyTagged++;
            return;
        }
        if (blockOwnerMap[d.blockId]) {
            resolvable++;
        } else {
            unresolvable++;
            if (unresolvableSamples.length < 5) unresolvableSamples.push({ id: doc.id, data: d });
        }
    });

    console.log(`  Total documents         : ${snap.size}`);
    console.log(`  Already have userId     : ${alreadyTagged}`);
    console.log(`  Resolvable (via blockId): ${resolvable}`);
    console.log(`  Unresolvable (orphan block): ${unresolvable}`);

    if (unresolvableSamples.length > 0) {
        console.log(`\n  Unresolvable samples (their block has no userId):`);
        unresolvableSamples.forEach(({ id, data }) =>
            console.log(sampleRow(id, data, ['blockId', 'severity', 'title', 'resolved']))
        );
        console.log('\n  Fix: first migrate orphan blocks with --fallback-owner=<uid>,');
        console.log('       then re-run this script to resolve these alerts.');
    }

    return { total: snap.size, alreadyTagged, resolvable, unresolvable };
}

// ─── Phase 2: Migrate blocks ─────────────────────────────────────────────────

async function migrateBlocks(orphanIds, blockOwnerMap) {
    if (orphanIds.length === 0) {
        console.log('\n✅  blocks — no orphans, nothing to do.');
        return { updated: 0 };
    }

    if (!FALLBACK_OWNER) {
        console.log(`\n⏭️  blocks — ${orphanIds.length} orphan(s) skipped (no --fallback-owner supplied).`);
        return { updated: 0 };
    }

    if (DRY_RUN) {
        console.log(`\n[DRY RUN] blocks — would update ${orphanIds.length} document(s) with userId="${FALLBACK_OWNER}".`);
        return { updated: 0 };
    }

    console.log(`\n🔄  blocks — stamping ${orphanIds.length} document(s) with userId="${FALLBACK_OWNER}"...`);

    let { batch, opCount } = { batch: db.batch(), opCount: 0 };
    let updated = 0;

    for (const docId of orphanIds) {
        batch.update(db.collection('blocks').doc(docId), { userId: FALLBACK_OWNER });
        // Also update the in-memory map so alert migration can use it immediately.
        blockOwnerMap[docId] = FALLBACK_OWNER;
        opCount++;
        updated++;

        if (opCount >= BATCH_SIZE) {
            ({ batch, opCount } = await commitBatch(batch, opCount));
            process.stdout.write(`    committed ${updated} so far…\r`);
        }
    }

    await commitBatch(batch, opCount);
    console.log(`  ✅  blocks — ${updated} document(s) updated.           `);
    return { updated };
}

// ─── Phase 2: Migrate monitoring_alerts ──────────────────────────────────────

async function migrateAlerts(blockOwnerMap) {
    console.log('\n🔄  monitoring_alerts — scanning...');

    const snap = await db.collection('monitoring_alerts').get();

    let { batch, opCount } = { batch: db.batch(), opCount: 0 };
    let processed  = 0;
    let updated    = 0;
    let skipped    = 0;
    let alreadyHad = 0;

    for (const doc of snap.docs) {
        const d = doc.data();
        processed++;

        // Rule 1: never overwrite an existing userId
        if (d.userId) {
            alreadyHad++;
            continue;
        }

        // Rule 2: resolve via blockId → block owner
        const ownerUid = blockOwnerMap[d.blockId];
        if (!ownerUid) {
            skipped++;
            continue;
        }

        updated++;

        if (!DRY_RUN) {
            batch.update(doc.ref, { userId: ownerUid });
            opCount++;

            if (opCount >= BATCH_SIZE) {
                ({ batch, opCount } = await commitBatch(batch, opCount));
                process.stdout.write(`    committed ${updated} so far…\r`);
            }
        }
    }

    if (!DRY_RUN) {
        await commitBatch(batch, opCount);
        console.log(`  ✅  monitoring_alerts — ${updated} updated, ${skipped} skipped, ${alreadyHad} already tagged.`);
    } else {
        console.log(`[DRY RUN] monitoring_alerts — would update ${updated}, skip ${skipped}, leave ${alreadyHad} unchanged.`);
    }

    return { processed, updated, skipped, alreadyHad };
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
    console.log('╔══════════════════════════════════════════════════════════════╗');
    console.log('║        PineVision — userId Migration Script                  ║');
    console.log('╚══════════════════════════════════════════════════════════════╝');
    console.log(`\n  Mode    : ${DRY_RUN ? 'DRY RUN — inspect only, no writes' : '⚠️  LIVE WRITE MODE'}`);
    if (FALLBACK_OWNER) console.log(`  Fallback: ${FALLBACK_OWNER}`);
    console.log(`  Batch   : up to ${BATCH_SIZE} ops per commit`);

    // ── Inspect ──────────────────────────────────────────────────────
    const { total: bTotal, orphanIds, blockOwnerMap } = await inspectBlocks();
    const { total: aTotal, alreadyTagged, resolvable, unresolvable } =
        await inspectAlerts(blockOwnerMap);

    // ── Plan summary ─────────────────────────────────────────────────
    console.log('\n━━━  MIGRATION PLAN  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`  blocks            : ${orphanIds.length} to update` +
        (orphanIds.length > 0 && !FALLBACK_OWNER ? '  ← add --fallback-owner to include' : ''));
    console.log(`  monitoring_alerts : ${resolvable} to update, ${unresolvable} unresolvable (skipped)`);
    console.log(`  scans             : NOT TOUCHED`);

    if (DRY_RUN) {
        console.log('\n  ─────────────────────────────────────────────────────────');
        console.log('  DRY RUN complete — no data was changed.');
        console.log('\n  When ready, execute the migration with:');
        console.log('    node migrate-user-ids.js --run');
        if (orphanIds.length > 0) {
            console.log('\n  To also fix orphan blocks:');
            console.log('    node migrate-user-ids.js --run --fallback-owner=<uid>');
        }
        process.exit(0);
    }

    // ── Execute ───────────────────────────────────────────────────────
    console.log('\n  Proceeding with live writes...\n');

    // Migrate blocks first; blockOwnerMap is mutated in-place if orphans are fixed,
    // so the alert migration immediately benefits from the updated map.
    const blockResult = await migrateBlocks(orphanIds, blockOwnerMap);
    const alertResult = await migrateAlerts(blockOwnerMap);

    // ── Final report ─────────────────────────────────────────────────
    console.log('\n━━━  RESULT  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(`  blocks            : ${blockResult.updated} updated`);
    console.log(`  monitoring_alerts : ${alertResult.updated} updated | ` +
        `${alertResult.skipped} skipped | ${alertResult.alreadyHad} already had userId`);
    console.log('  scans             : NOT TOUCHED ✓');
    console.log('\n  ✅  Migration complete.\n');

    if (alertResult.skipped > 0) {
        console.log(`  ⚠️  ${alertResult.skipped} alert(s) remain unresolved (their block still has no userId).`);
        console.log('      Re-run with --fallback-owner=<uid> to fix their parent blocks,');
        console.log('      then run this script once more.\n');
    }
}

main().catch(err => {
    console.error('\n❌  Fatal error:', err.message);
    process.exit(1);
});
