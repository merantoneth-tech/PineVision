# PineVision — Features Summary

---

## 1. Implemented Features

### Authentication
**Belongs to:** Both Admin and Client

Firebase-powered email and password authentication. Users log in through a single login page and are automatically routed to the correct interface based on their assigned role (Admin or Client). Sessions persist across browser refreshes. No separate registration flow — accounts are created by admins.

---

### Real-Time Drone Detection
**Belongs to:** Client (Drone View page)

The flagship feature of PineVision. A DJI drone streams live video via RTMP to a local MediaMTX server, which converts it to an HLS stream playable in the browser. The Flask backend pulls 1 frame per second from this stream and runs a custom-trained YOLOv5 model against each frame, classifying every pineapple detected into one of three categories:

- **Bearing** — Plants that are fruit-ready and productive
- **Non-Bearing** — Plants present but not yet producing fruit
- **Non-Viable** — Plants that are diseased, dying, or otherwise unproductive

Live counts and percentages update on the client's screen every two seconds via Firebase real-time listeners.

---

### Duplicate Detection Prevention
**Belongs to:** Client (Detection Engine)

DeepSORT (Deep Simple Online and Realtime Tracking) is integrated into the detection pipeline to assign unique IDs to each detected pineapple and track them across consecutive frames. This prevents the same plant from being counted multiple times as the drone moves over it, ensuring that final counts are accurate rather than inflated.

---

### Fruit Block Management
**Belongs to:** Client

Clients can browse and manage all plantation blocks assigned to their account. Each block contains metadata (area, section, declared plant population) and maintains running statistics from the latest scan (bearing %, non-bearing %, non-viable %). Blocks serve as the unit of organisation for all scans and alerts.

---

### Scan Session Management
**Belongs to:** Client (and viewable by Admin)

Each drone survey is recorded as a scan session linked to a specific block and user. Sessions track start and end time, live detection counts throughout the flight, and a final summary upon completion. The full scan history is stored in Firestore and accessible for review at any time.

---

### Automated Alert System
**Belongs to:** Both (generated automatically, visible to both Admin and Client)

The system continuously monitors detection percentages during active scans and compares them against configurable thresholds. Alerts are created automatically when values breach these thresholds:

| Condition | Severity |
|-----------|---------|
| Bearing rate < 60% | CRITICAL |
| Non-bearing rate > 25% | CRITICAL |
| Non-viable rate > 15% | CRITICAL |
| Other threshold breaches | WARNING |

Alerts auto-resolve when values return to safe levels. Both clients (for their own blocks) and admins (system-wide) can view alert history.

---

### User Management
**Belongs to:** Admin only

Admins have full control over all user accounts in the system. They can create new client or admin accounts, edit user details, assign roles and permissions, reset passwords, and enable or disable accounts without deleting them. User status (Active/Disabled) is reflected across the system immediately.

---

### Reports & Data Export
**Belongs to:** Both Admin and Client

Both admins and clients can generate reports from scan data. Reports can be filtered by date range and block. Export formats include CSV (confirmed) and PDF (may be partially implemented). Admins see system-wide data; clients see only their own blocks' data.

---

### Audit Logs & Activity Tracking
**Belongs to:** Admin only

A complete audit trail is maintained for all significant user actions (logins, scan starts/stops, user changes, settings updates). This is split across two pages — an Activity Log for a human-readable timeline and Audit Logs for a more structured, detailed event record. Used for compliance, accountability, and troubleshooting.

---

### Settings & Preferences
**Belongs to:** Both Admin and Client

Both user types have a Settings page. Clients manage their personal profile, password, and display preferences. Admins additionally manage system-wide configuration including alert threshold values.

---

## 2. Excluded / Missing Features

### Not Yet Implemented

| Feature | Notes |
|---------|-------|
| Mobile Application | System is web-only; no native iOS or Android app |
| Multi-Farm / Multi-Tenant Support | No visible support for managing multiple separate farms under one platform |
| Payment / Subscription Management | No billing, pricing plans, or subscription features |
| Offline Mode | Requires live internet connection to Firebase at all times |
| Drone Flight Path Planning | No automated flight path scheduling or waypoint management |
| Weather / Environmental Data | No integration with weather APIs or environmental sensors |
| Predictive Analytics / Yield Forecasting | No AI-based forecasting from historical scan data |
| Push Notifications | Alerts exist in-app but no browser push or email/SMS notification system |
| Multi-Language Support | Interface appears English-only |
| Dark Mode | No confirmed theme toggle (may exist via utils.js but unconfirmed) |

### Partially Implemented or Placeholder

| Feature | Status |
|---------|--------|
| PDF Report Export | Export button may exist but PDF generation may be a stub |
| Flight Management Page | Exists but may overlap with or defer to the Drone View workflow |
| Block Creation / Editing | Block data appears to be pre-seeded; no clear UI for creating new blocks |
| Permissions System | Permission fields exist on user accounts but granular permission enforcement may be incomplete |

---

## 3. System Modules Summary

| Module | Who Uses It | What It Does |
|--------|------------|-------------|
| **Authentication Module** | All users | Login, session management, role-based routing |
| **Drone Detection Module** | Client | RTMP stream → HLS conversion → YOLOv5 inference → real-time counts |
| **Object Tracking Module** | Client (backend) | DeepSORT tracking to prevent duplicate pineapple counts |
| **Block Management Module** | Client | View and manage plantation block inventory and stats |
| **Scan Session Module** | Client + Admin | Create, track, and store drone scan sessions |
| **Alert Engine** | Automated + both roles | Threshold monitoring, alert creation, auto-resolution |
| **User Management Module** | Admin | Full CRUD for user accounts and roles |
| **Reporting Module** | Both | Data export and analytics from scan history |
| **Audit Module** | Admin | Activity logs, audit trails, compliance records |
| **Settings Module** | Both | Personal preferences (client) and system config (admin) |

---

## 4. Overall System Flow

```
[Login] 
    ↓
[Role Check]
    ├── Admin → Admin Dashboard → Manage Users / View All Scans / Alerts / Reports / Audit Logs
    └── Client → Client Dashboard
                    ↓
              [Select Fruit Block]
                    ↓
              [Drone View Page]
                    ↓
              [Connect Drone via RTMP URL]
                    ↓
              [Live Video Stream + Real-Time AI Detection Starts]
                    ↓
              [Bearing / Non-Bearing / Non-Viable counts update live]
                    ↓
              [End Scan → Results saved to Firebase]
                    ↓
              [Alerts auto-generated if thresholds breached]
                    ↓
              [View Scan History / Reports / Alerts]
```
