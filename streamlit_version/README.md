# AI Travel Planner

An AI-powered travel planning web app built with Streamlit, MySQL, and OpenAI.

---

## Quick Links

| Link | URL |
|------|-----|
| App (user login) | `http://localhost:8501` |
| phpMyAdmin | `http://localhost/phpmyadmin` |

> **Admin Portal Link (share privately with the admin only)**
>
> ```
> http://localhost:8501/?portal=admin
> ```
>
> This URL is not shown anywhere in the app. Send it directly and confidentially to the designated administrator. The admin uses it to register their account and log in to the Admin Dashboard.

---

## Requirements

- Python 3.9+
- MySQL Server (via XAMPP, WAMP, or standalone)
- phpMyAdmin (optional, for GUI database management)

---

## Installation

```powershell
pip install -r requirements.txt
```

Or install manually:

```powershell
pip install streamlit openai reportlab plotly requests mysql-connector-python
```

---

## Database Setup

1. Start your MySQL server (e.g. start XAMPP and enable MySQL).
2. Open **phpMyAdmin** at `http://localhost/phpmyadmin`.
3. Click **Import** → **Choose File** → select `travel_planner.sql` → click **Go**.

The schema creates the `travel_planner` database with four tables:
`users`, `admins`, `itineraries`, `expenses`.

The app also auto-creates the database and seeds default accounts on first run.

### Database connection settings

Edit the `DB_*` block at the top of `app.py` if your MySQL credentials differ:

```python
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "travel_planner"
DB_USER = "root"
DB_PASS = ""          # blank by default in XAMPP
```

---

## API Keys

Set these as environment variables before running the app.

**Windows PowerShell:**

```powershell
$env:OPENAI_API_KEY  = "sk-your-openai-key"
$env:WEATHER_API_KEY = "your-openweathermap-key"
$env:SMTP_USER       = "your@gmail.com"
$env:SMTP_PASS       = "your-gmail-app-password"
```

| Variable | Where to get it | Required |
|----------|----------------|----------|
| `OPENAI_API_KEY` | platform.openai.com | Yes — powers all AI features |
| `WEATHER_API_KEY` | openweathermap.org (free) | Yes — weather & forecast |
| `SMTP_USER` | Your Gmail address | No — only for email PDF |
| `SMTP_PASS` | Google Account → Security → App Passwords | No — only for email PDF |

---

## Running the App

```powershell
python -m streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Login Credentials

### User Login
URL: `http://localhost:8501`

| Username | Password | Role |
|----------|----------|------|
| traveler | Travel@123 | Demo User |

**Users can self-register** on the login page ("Create Account" tab). Registration requires:
- Full name
- Username (3+ characters, letters/numbers/underscore only)
- Email address (required, must be unique)
- Password (6+ characters, at least one number)

After registering, a **verification email** is sent to the user's inbox. The user must click the link in that email to activate their account before they can sign in.

After verifying, users can sign in using either their **username** or **email address**.

### Email Verification Flow
1. User fills in the Create Account form and submits
2. App creates the account with `verified=0` and sends an email containing a unique link
3. User opens the email and clicks **"Verify My Email"**
4. App sets `verified=1` and shows a success message
5. User signs in normally

> **Note:** The verification link uses `APP_URL` (default `http://localhost:8501`). Set the `APP_URL` environment variable if you deploy the app publicly.

### Admin Login

> **This link must be shared privately — it is not accessible from the user login page.**

URL: `http://localhost:8501/?portal=admin`

| Username | Password | Role |
|----------|----------|------|
| admin | Admin@1234 | Admin |

**Change the default password immediately after first login.**

The admin uses the **Register Admin** tab at the same URL to create their account.
Admin password rules: 8+ characters, one uppercase letter, one number, one special character.

---

## File Structure

```
project/
│
├── app.py                  ← Main application (single file, ~2300 lines)
├── requirements.txt        ← Python dependencies
├── travel_planner.sql      ← MySQL schema — import in phpMyAdmin
└── README.md               ← This file
```

---

## Feature List

### Authentication
- Separate `users` and `admins` MySQL tables
- PBKDF2-SHA256 password hashing (260,000 iterations)
- User self-registration with password strength indicator
- Admin registration at `?portal=admin` (stricter password policy)
- Split-screen login page (user) / dark admin portal page
- Password change from Settings

### Trip Planner
- AI day-by-day itinerary generation (OpenAI GPT)
- Destination, days, start date, budget, traveler count
- 8 travel styles (Budget Backpacker to Luxury Traveler)
- Live weather shown inline after generating
- Auto-save to database after generation

#### Advanced Options
- Group type (Solo, Couple, Family, Corporate)
- Trip theme (Cultural, Culinary, Adventure, Wellness, etc.)
- Accommodation type, transport mode, meal preference
- Trip pace and fitness level
- Day start time, restaurant meals per day
- Eco-friendly and pet-friendly toggles
- Nightlife and off-peak preferences
- Must-visit spots and places to avoid
- Budget priority (accommodation, food, activities, transport)
- Display currency (USD, EUR, GBP, AUD, CAD, JPY, AED, SGD, INR, MYR, LKR)
- Extra content sections: local phrases, visa info, safety contacts, health tips, photo spots, day trips, local events

### Places & Recommendations
- AI hotel suggestions globally
- AI restaurant suggestions globally
- AI attraction suggestions globally
- Filter by travel style, budget, currency, dietary preference, travelers

### AI Tools
- Surprise destination generator
- Local phrases & language guide
- Packing list generator
- Budget saving tips
- Side-by-side trip comparison

### Saved Itineraries
- Search by destination
- Sort by newest, oldest, budget, days
- Star/favourite trips
- Reload trip to planner
- Delete trips
- PDF download per trip

### Expense Tracker
- Log expenses by category per trip
- Budget vs actual progress bar with colour coding
- Over-90% overspend warning
- Bar chart (spent vs budget)
- Delete individual expenses
- Expenses included in PDF export

### PDF Export
- Professional multi-section PDF (ReportLab)
- Trip summary table
- Full itinerary with formatted day headers
- Packing list section (if generated)
- Expense tracker summary table
- Footer with generation date

### Email
- Email PDF as attachment to any address via Gmail SMTP

### Weather
- Live current conditions (OpenWeatherMap)
- Temperature, humidity, wind, feels-like
- 5-day forecast cards
- Weather shown inline on planner page after generating

### Analytics
- Total trips, total days, average budget, unique destinations
- Budget per trip bar chart
- Travel style pie chart
- Trip timeline (Gantt chart)
- Trip length histogram

### Admin Panel (Settings → Admin tab)
- View and remove regular users
- View and remove admin accounts (default `admin` is protected)
- View all itineraries across all users
- Accessible only when logged in as admin

### UI / UX
- Green and white theme
- Split-screen login layout
- Sidebar navigation with floating toggle button (☰ to open, ✕ to close) — always visible and clickable even when the sidebar is collapsed
- Responsive columns and metric cards
- Custom CSS throughout
- No emoji icons in UI text

---

## Sidebar Navigation

The sidebar on the left shows all navigation buttons for both the **User Panel** and **Admin Panel**:

- Dashboard
- Plan a Trip
- My Itineraries
- Expense Tracker
- Analytics
- Weather
- Places
- AI Tools
- Settings
- Admin Dashboard *(admin accounts only)*
- Sign Out

The sidebar is kept permanently visible using CSS (`transform: translateX(0) !important`) so it cannot be accidentally hidden. If Streamlit's internal collapse button is clicked and the sidebar disappears, a large **green arrow button** appears at the left edge of the screen — click it to reopen the sidebar instantly.

---

## Database Schema

```
travel_planner
│
├── users          username (PK), password_hash, full_name, email,
│                  avatar, pref_currency, last_login, created_at
│
├── admins         username (PK), password_hash, full_name, email,
│                  last_login, created_at
│
├── itineraries    id (PK), user (FK→users), destination, days,
│                  start_date, budget, travelers, travel_type,
│                  activities, notes, accommodation, transport,
│                  meal_pref, pace, fitness, must_visit, avoid,
│                  group_type, kids_ages, eco, pet, trip_theme,
│                  day_start, restaurant_meals, nightlife, off_peak,
│                  budget_priority, currency, itinerary, packing_list,
│                  saved_on, starred, created_at
│
└── expenses       id (PK), itinerary_id (FK→itineraries), user,
                   date, category, description, amount, created_at
```
