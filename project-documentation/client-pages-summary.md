# PineVision — Client Pages Summary

Client pages are accessible to users with the **Client** role. They provide tools for conducting drone scans, monitoring crop health, and reviewing scan history for blocks under the client's management.

---

## Login Page

**Page:** `index.html`

### Purpose
The public-facing entry point for all users. Provides authentication before granting access to any part of the system.

### Main Functionalities
- Email and password login via Firebase Authentication
- Automatic role-based redirect after login (Client → client dashboard, Admin → admin dashboard)
- Session persistence so users stay logged in across browser refreshes

### Key UI Sections
- Login form (email, password fields)
- System branding and version indicator (v2.4)
- Submit button with loading state

---

## Client Dashboard

**Page:** `client/dashboard.html`

### Purpose
The main landing page for client users after login. Gives a quick overview of their farm's current status and recent activity.

### Main Functionalities
- Displays key metrics: total blocks, recent scan count, alert summary, overall bearing percentage
- Shows recent scan activity and latest results
- Provides quick-access navigation to all client sections
- Highlights any open alerts requiring attention

### Key UI Sections
- Summary cards (blocks count, scan count, alert count, bearing %)
- Recent scans feed
- Navigation sidebar
- Alert banner (if critical alerts are open)

---

## Fruit Blocks

**Page:** `client/blocks.html`

### Purpose
The inventory view of all fruit blocks (plantation sections) assigned to the client. Used as the starting point before initiating a scan.

### Main Functionalities
- View all blocks with their key stats (area, plant count, last scan date, bearing percentage)
- Filter or search blocks by name, section, or status
- Click into any block for detailed information
- Navigate directly from a block to start a scan

### Key Actions Users Can Do
- Browse all blocks at a glance
- Filter blocks to find specific sections
- Click a block to open its detail view

### Key UI Sections
- Block cards or table rows with key metrics
- Filter/search bar
- Status badges (Healthy / Warning / Critical based on bearing rates)
- Link to individual block detail view

---

## Block Detail View

**Page:** `client/blocks-view.html`

### Purpose
A deep-dive view into a single fruit block. Shows all available data for one specific block and links to its scan history.

### Main Functionalities
- Displays block metadata (area, section, total plants, declared population)
- Shows current bearing/non-bearing/non-viable percentages
- Lists all past scans performed on this block
- Provides direct access to start a new drone scan for this block

### Key Actions Users Can Do
- Review the full scan history for the block
- See the block's current health status at a glance
- Navigate to the Drone View to begin a new scan

### Key UI Sections
- Block info panel (name, area, section, plant count)
- Current health metrics (bearing %, non-bearing %, non-viable %)
- Scan history table for this block
- "Start Scan" / "Drone View" action button

---

## Drone View (Live Detection)

**Page:** `client/drone-view.html`

### Purpose
The core operational page of PineVision. This is where the actual drone scan happens — streaming live video and showing real-time AI detection results.

### Main Functionalities
- Connect to a live DJI drone RTMP stream
- Display the live drone video feed in the browser (via HLS)
- Show real-time detection statistics updating every 2 seconds:
  - Total pineapples detected
  - Bearing count and percentage
  - Non-bearing count and percentage
  - Non-viable count and percentage
- Prevent duplicate counts using DeepSORT tracking
- End the scan and save all results to the database
- Auto-generate alerts if thresholds are breached during the scan

### Key Actions Users Can Do
- Enter the drone's RTMP stream URL and connect
- Watch the live video feed with detection overlay
- Monitor live counts in real time
- Stop/end the scan session when the flight is complete

### Key UI Sections
- Video player panel (HLS live stream)
- Real-time stats panel (4 metric counters with live updates)
- Connection control (RTMP URL input, Connect button)
- End Scan button
- Status indicators (Connected / Detecting / Idle)

---

## Scans

**Page:** `client/scans.html`

### Purpose
A complete log of all drone scan sessions performed by the client. Used for reviewing historical results and tracking trends over time.

### Main Functionalities
- View all past completed scans in a list/table format
- Filter scans by block, date range, or outcome
- Click into individual scan records for full results
- Export scan data for reporting purposes

### Key Actions Users Can Do
- Search for a specific scan by block or date
- Review the detailed results of any past scan
- Export scan records

### Key UI Sections
- Scans table (block name, scan date, duration, bearing %, total count)
- Filter controls (date picker, block selector)
- Row-click to expand or navigate to full scan detail
- Export button

---

## Flight Management

**Page:** `client/flight.html`

### Purpose
Manages formal flight/scan sessions, providing a structured view of ongoing and scheduled drone operations.

### Main Functionalities
- View current or recently created flight sessions
- Create a new flight session linked to a specific block
- Track session status (pending, active, completed)
- Link flight sessions to scan records

### Key UI Sections
- Flight sessions list with status badges
- Create new flight session form
- Block selector and session details

---

## Reports

**Page:** `client/reports.html`

### Purpose
Allows clients to generate and export reports from their own scan and block data for farm management and record-keeping purposes.

### Main Functionalities
- Select a date range and blocks to include in the report
- View summarized analytics (bearing trends, scan frequency, block comparisons)
- Export reports as CSV or PDF

### Key UI Sections
- Report configuration panel (date range, block filters)
- Analytics summary cards and charts
- Export buttons (CSV / PDF)

---

## Alerts

**Page:** `client/alerts.html`

### Purpose
Displays all alerts generated for the client's blocks. Lets clients stay informed about crop health issues that require attention.

### Main Functionalities
- View all open and resolved alerts for blocks the client manages
- See alert severity (CRITICAL / WARNING)
- Understand what threshold was breached and on which block
- Track when alerts were created and when they were resolved

### Key Actions Users Can Do
- Review which blocks currently have critical issues
- See the history of past alerts and their resolution status

### Key UI Sections
- Alert list with severity badges
- Block name and alert description
- Created / Resolved timestamps
- Status filter (Open / Resolved / All)

---

## Settings

**Page:** `client/settings.html`

### Purpose
Personal account and preference settings for the client user.

### Main Functionalities
- Update profile information (name, email)
- Change account password
- Configure notification or display preferences
- Manage personal account settings

### Key UI Sections
- Profile edit form
- Password change section
- Notification/display preference toggles
- Save changes button
