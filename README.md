# 📊 Excel Analytics Pro

**Industry-grade, AI-powered Excel and CSV analysis platform**

Full-stack SaaS application with professional UI, Gemini AI integration, Stripe payments, JWT authentication, and downloadable reports.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **File Upload** | Excel (.xlsx, .xls, .xlsm), CSV · Max 50MB |
| **Structural Analysis** | Rows, columns, sheets, missing data, duplicates, quality score |
| **6 Analysis Types** | Summary stats, data quality, distribution, categories, correlation, AI insights |
| **Gemini AI** | Narrative analysis, pattern detection, recommendations |
| **Payment Gating** | Free preview for all · Download requires plan or credits |
| **Stripe Checkout** | Plans + à-la-carte credits (demo mode available) |
| **Auth & Security** | JWT (access + refresh), bcrypt, rate limiting, screen capture prevention |
| **Reports** | PDF (ReportLab) + Excel (openpyxl) reports |
| **Responsive** | Mobile, tablet, desktop — any screen size |

---

## 🚀 Quick Start

### Requirements
- **Python 3.9+**
- **Node.js 18+**
- **npm**

### 1. Setup (first time only)
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Configure API Keys (optional but recommended)

Edit `backend/.env`:

```env
GEMINI_API_KEY=your-key-from-aistudio.google.com
STRIPE_SECRET_KEY=sk_test_...        # Leave blank for demo mode
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

**Getting API keys:**
- **Gemini AI** → https://aistudio.google.com/app/apikey (free)
- **Stripe** → https://dashboard.stripe.com/test/apikeys (test keys are free)

### 3. Start the application
```bash
./start.sh
```

Or start separately:
```bash
# Terminal 1 - Backend
./start-backend.sh

# Terminal 2 - Frontend  
./start-frontend.sh
```

### 4. Open in browser
```
http://localhost:3000
```

---

## 📁 Project Structure

```
excel-analytics-platform/
├── backend/
│   ├── app.py                 # Flask app factory
│   ├── database.py            # SQLAlchemy models
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # Configuration
│   ├── routes/
│   │   ├── auth.py            # Register, login, JWT refresh
│   │   ├── excel.py           # Upload, list, delete, preview
│   │   ├── analysis.py        # Run 6 analysis types + AI
│   │   ├── reports.py         # PDF/Excel report generation
│   │   ├── payment.py         # Stripe + demo activate
│   │   └── user.py            # Profile, dashboard stats
│   └── services/
│       └── excel_service.py   # Parsing, quality scoring
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Router + route guards
│   │   ├── main.jsx           # Entry point
│   │   ├── index.css          # Global styles + Tailwind
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── UploadPage.jsx
│   │   │   ├── FilesPage.jsx
│   │   │   ├── AnalysisPage.jsx
│   │   │   ├── PricingPage.jsx
│   │   │   └── ProfilePage.jsx
│   │   ├── components/
│   │   │   └── layout/AppLayout.jsx
│   │   ├── store/
│   │   │   └── authStore.js   # Zustand auth state
│   │   └── utils/
│   │       └── api.js         # Axios with JWT refresh
│   ├── package.json
│   └── vite.config.js
├── uploads/                   # Uploaded files (auto-created)
├── reports/                   # Generated reports (auto-created)
├── setup.sh                   # First-time setup
├── start.sh                   # Start both servers
├── start-backend.sh
└── start-frontend.sh
```

---

## 🔑 Environment Variables

```env
# backend/.env

SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
FLASK_ENV=development
PORT=5000

# Optional: Gemini AI
GEMINI_API_KEY=AIza...

# Optional: Stripe (leave blank for demo mode)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

FRONTEND_URL=http://localhost:3000
```

---

## 💳 Pricing Plans

| Plan | Price | Files | Credits |
|------|-------|-------|---------|
| Free | $0 | 5 | 3 (on signup) |
| Basic | $9.99/mo | 25 | 20/month |
| Pro | $24.99/mo | 100 | 100/month |
| Enterprise | $79.99/mo | Unlimited | 500/month |
| 10 Credits | $4.99 | — | +10 |

**Demo mode**: If Stripe keys are not set, the "Upgrade" button instantly activates plans for testing.

---

## 🔒 Security Features

- **JWT** access tokens (1 hour) + refresh tokens (30 days)
- **bcrypt** password hashing (12 rounds)
- **Rate limiting**: 200 req/hour, 50 req/minute
- **Input validation**: Email format, password strength (uppercase, lowercase, number, special char)
- **File validation**: Type checking, size limits, secure filename generation
- **CORS**: Configured for frontend origin only
- **Watermark overlay**: Preview content shows "PREVIEW ONLY" watermark
- **Screen capture prevention**: CSS `user-select: none`, `print` watermark, keyboard shortcut blocking

---

## 📊 Analysis Types

| Type | Free | Description |
|------|------|-------------|
| Summary Statistics | ✅ | Mean, median, std, min, max per numeric column |
| Data Quality | ✅ | Missing data, duplicates, quality score |
| Distribution | ✅ | Box plot stats, outliers, skewness, kurtosis |
| Category Analysis | ✅ | Value counts, frequency distribution |
| Correlation Matrix | 🔒 | Pearson correlation between all numeric columns |
| AI Insights | 🔒 | Gemini AI narrative analysis (uses credits on free plan) |

---

## 🛠 Tech Stack

**Backend**: Python · Flask · SQLAlchemy · SQLite · JWT · Bcrypt · Gemini AI · Stripe · ReportLab · openpyxl · pandas · numpy

**Frontend**: React 18 · Vite · Tailwind CSS · Recharts · Zustand · Axios · react-dropzone · lucide-react

---

## 🐳 Production Deployment

For production, consider:
1. Switch `DATABASE_URL` to PostgreSQL
2. Use environment variables (never commit `.env`)
3. Set `FLASK_ENV=production`
4. Build frontend: `cd frontend && npm run build`
5. Serve frontend with nginx or Python's `send_from_directory`
6. Use gunicorn: `gunicorn -w 4 app:create_app()`



run the backed 
coomend
cd backend
venv\Scripts\activate
python app.py

for frontend 
cd frontend
npm run dev

