# PineVision — System Summary

---

## 1. System Overview

### What the System Is

**PineVision** is a smart farm monitoring and management platform designed for pineapple plantation operations. It combines live drone video streaming with AI-powered object detection to give farm owners and managers real-time visibility into the health and productivity of their crops.

### Main Purpose

PineVision automates the process of surveying pineapple fields. Instead of walking blocks manually, farm operators fly a drone over a block and the system counts and classifies every visible pineapple in real time — distinguishing between fruit-ready plants, non-bearing plants, and diseased/non-viable plants.

### Target Users

| Role | Who They Are |
|------|-------------|
| **Admin** | System administrators, IT managers, or farm management supervisors responsible for overseeing operations, managing accounts, and reviewing system-wide data |
| **Client** | Farm operators, agronomists, or field supervisors who conduct drone scans and review block-level results |

### Main Problem It Solves

Traditional pineapple field surveys are time-consuming, labour-intensive, and prone to human error. PineVision replaces manual headcounts with automated AI detection from drone footage — delivering accurate, real-time crop counts across entire plantation blocks in a single drone flight.

### General System Workflow

1. A client logs in and selects a fruit block to survey.
2. They navigate to the Drone View page and connect a DJI drone via its RTMP stream.
3. The system begins AI-powered detection automatically, classifying pineapples frame by frame.
4. Live statistics (bearing %, non-bearing %, non-viable %) update on screen every two seconds.
5. When the flight is complete, the client ends the scan — results are saved to the database instantly.
6. The system auto-generates alerts if any metric falls outside safe thresholds.
7. Admins can review all scans, user activity, and system-wide reports from the admin dashboard.

---

## 2. Technology Stack (High-Level)

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML, CSS, Bootstrap 5, JavaScript |
| Backend | Python (Flask) |
| Database | Firebase Firestore (NoSQL) |
| Authentication | Firebase Authentication |
| AI Detection | YOLOv5 (custom trained model) |
| Object Tracking | DeepSORT (prevents duplicate counting) |
| Video Streaming | RTMP → HLS via MediaMTX |
| Video Processing | FFmpeg + OpenCV |

---

## 3. System Modules

### Authentication Module
Handles login and session management using Firebase Authentication. Role-based routing ensures admins and clients see different interfaces after login.

### Drone Detection Module
The core engine of the system. Connects to a live drone RTMP stream, converts it to HLS for browser playback, and runs YOLOv5 inference at 1 frame per second to classify pineapples. DeepSORT tracking prevents the same plant from being counted more than once across multiple frames.

### Block Management Module
Manages the plantation's fruit blocks (sections of land). Each block stores metadata such as area, total plant count, current scan statistics, and health percentages.

### Scan Management Module
Tracks individual drone scan sessions from start to finish. Records scan start/end times, block scanned, operator, and final counts. Builds a complete scan history over time.

### Alert Management Module
Automatically generates alerts when detection thresholds are breached (e.g. bearing rate drops below 60%). Alerts auto-resolve when values return to safe levels.

### Reporting Module
Provides data export and analytics tools. Clients and admins can generate reports from scan data for record-keeping and farm planning purposes.

### User Management Module *(Admin only)*
Full user account lifecycle management — creating, editing, enabling, and disabling client accounts. Role and permission assignment is controlled here.

### Audit & Activity Module *(Admin only)*
Maintains a complete audit trail of all user actions and system events, supporting compliance and accountability requirements.

---

## 4. User Roles

### Admin
- Full system visibility across all users and blocks
- Manage all user accounts (create, edit, disable)
- View system-wide scan activity and alerts
- Access audit logs and activity trails
- Configure system-level settings

### Client
- Access their assigned fruit blocks
- Connect drone and conduct real-time scans
- View live detection statistics during flights
- Review personal scan history
- Receive and manage their own alerts
- Manage personal account settings

---

## 5. System Version

**Version 2.4** — as indicated on the login page.

---

## 6. External Integrations

| Integration | Purpose |
|-------------|---------|
| Firebase (Auth + Firestore) | Authentication, real-time database, data persistence |
| DJI Drone | Hardware source of RTMP video stream |
| MediaMTX | Converts RTMP drone stream to browser-playable HLS |
| YOLOv5 | AI model for pineapple classification |
| DeepSORT | Multi-object tracking to prevent duplicate counts |
| FFmpeg | Video frame extraction from HLS stream |

---

## 7. What Is Not Yet Implemented

- No payment or subscription management system
- No multi-farm / multi-tenant support visible
- No mobile application (web-only)
- No offline mode or local data sync
- No weather or environmental data integration
- No predictive analytics or yield forecasting
- Some report export formats (PDF) may be placeholders
- No drone flight path planning or automation
