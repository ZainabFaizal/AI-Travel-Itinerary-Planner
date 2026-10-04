# AI Travel Itinerary Planner

An AI-powered travel planning project built in Python, available in **two versions** in one repository:

| Version | Folder | Interface | Best for |
|---|---|---|---|
| Terminal version | [`terminal_version/`](./terminal_version) | Command line | Quick planning, lightweight use |
| Streamlit version | [`streamlit_version/`](./streamlit_version) | Web app (Streamlit + MySQL) | Full-featured experience with logins, saved trips and reports |

---

## Repository Structure

```
AI-Travel-Itinerary-Planner/
├── terminal_version/        # Command-line travel planner
│   ├── main.py
│   ├── ai_assistant.py
│   ├── destination.py
│   ├── itinerary_manager.py
│   ├── data/
│   │   └── destinations.json
│   └── README.md
│
├── streamlit_version/       # Web app version (v2)
│   ├── app.py
│   ├── requirements.txt
│   ├── travel_planner.sql
│   └── README.md
│
├── .gitignore
└── README.md                # You are here
```

---

## 1. Terminal Version

A command-line app that helps you explore destinations, generate itineraries with an AI assistant, and manage your saved plans.

**Run it**

```bash
cd terminal_version
python main.py
```

**API keys**

Create a `.env` file inside `terminal_version/` and add your own keys (see `terminal_version/README.md` for the exact variable names). The `.env` file is ignored by Git and must never be uploaded.

---

## 2. Streamlit Version (v2)

A full web application built with **Streamlit**, **MySQL** and **OpenAI**.

**Main features**

- AI-generated day-by-day trip itineraries
- User registration and login, plus an admin panel
- Saved itineraries (search, sort, star, reload, delete)
- Expense tracker with budget progress and charts
- Live weather and 5-day forecast
- Hotel, restaurant and attraction suggestions
- Analytics dashboard
- PDF export of trips
- Optional email delivery of itineraries

**Requirements**

- Python 3.9+
- MySQL Server (via XAMPP, WAMP or standalone)
- phpMyAdmin (optional, for managing the database)

**Setup and run**

```bash
cd streamlit_version
pip install -r requirements.txt
```

1. Start MySQL (for example with XAMPP).
2. Import `travel_planner.sql` into MySQL (via phpMyAdmin: **Import → Choose File → Go**).
3. Set your API keys as environment variables.

   Windows PowerShell:
   ```powershell
   $env:OPENAI_API_KEY  = "your-openai-key"
   $env:WEATHER_API_KEY = "your-openweathermap-key"
   ```

4. Start the app:
   ```bash
   python -m streamlit run app.py
   ```

The app opens at `http://localhost:8501`.

For the full list of settings, login details and features, see [`streamlit_version/README.md`](./streamlit_version/README.md).

---

## Security Notes

- Never commit `.env` files, passwords or API keys.
- Change any default admin/demo passwords before sharing or deploying the app.
- If a key was ever uploaded to GitHub, regenerate it in the provider's dashboard.

---

## Author

**Zainab Faizal**
GitHub: [@ZainabFaizal](https://github.com/ZainabFaizal)
