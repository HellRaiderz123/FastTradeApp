# FastTradeApp — Self-Host Setup Guide

This guide covers everything needed to run your own private instance of FastTradeApp.
Each person runs their own copy — your broker credentials, trades, and data stay entirely on your own machine or server.

---

## Prerequisites

| Tool | Minimum Version | Download |
|------|----------------|----------|
| Docker Desktop | 4.x | https://www.docker.com/products/docker-desktop |
| Docker Compose | v2 (bundled with Docker Desktop) | — |
| Node.js | 18+ | https://nodejs.org (for mobile only) |
| Expo Go (phone) | latest | App Store / Play Store (for mobile only) |

> **Windows users**: Docker Desktop requires WSL 2. Enable it from Docker Desktop settings.

---

## Architecture

```
Your Machine / VPS
├── fasttrade-db        (PostgreSQL 16 — your data)
├── fasttrade-backend   (FastAPI — port 8000)
├── fasttrade-frontend  (React web UI — port 3000)
└── fasttrade-ollama    (Ollama LLM — port 11434, optional)

Your Phone
└── Expo Go app  →  connects to backend over LAN or tunnel
```

---

## Step 1 — Get the code

```bash
git clone https://github.com/yourname/FastTradeApp.git
cd FastTradeApp
```

---

## Step 2 — Configure your environment

```bash
cd backend
cp .env.example .env
```

Now open `backend/.env` and fill in **at minimum**:

### 2a. Zerodha credentials

1. Go to https://developers.kite.trade/ → **My Apps** → create an app.
2. Set the redirect URL to `http://127.0.0.1:8000/zerodha/callback` (or your server IP).
3. Copy **API Key** and **API Secret** into `.env`.

```env
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
```

### 2b. Auto-login (optional but recommended)

Enables daily 8 AM token refresh so you never have to manually re-authenticate.

```env
ZERODHA_USER_ID=your_zerodha_client_id      # e.g. AB1234
ZERODHA_PASSWORD=your_login_password
ZERODHA_TOTP_SECRET=your_totp_base32_secret  # raw Base32 key, NOT the 6-digit code
```

**How to get the TOTP secret:**
- In Zerodha > Profile > Security > Two-Factor Authentication
- When setting up a new TOTP authenticator, Zerodha shows a QR code AND the raw key underneath it
- Copy the raw key (looks like `DTLMEIX6NYOZCEAGLQMTZKJ3THZSDZJS`)

If you skip auto-login, you'll need to paste a fresh access token manually every morning before market open.

### 2c. Database password

Change the default password (used only internally by Docker):

```env
DATABASE_URL=postgresql://fasttrade:YOUR_STRONG_DB_PASSWORD@db:5432/fasttrade
```

Also update `docker-compose.yml` → `db.environment.POSTGRES_PASSWORD` to the same value.

### 2d. App authentication

Generate a secret key:

```bash
# Run this command and paste the output into AUTH_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

```env
AUTH_ENABLED=true
AUTH_USERNAME=admin
AUTH_PASSWORD=your_strong_password
AUTH_SECRET_KEY=paste_generated_key_here
```

### 2e. Execution mode

**Always start on paper trading:**

```env
EXECUTION_MODE=PAPER_TRADING
```

Switch to `ZERODHA_DRY_RUN` (logs orders, no fills) or `ZERODHA_LIVE` only after you have verified everything works.

### 2f. Risk limits (recommended defaults)

```env
RISK_PER_TRADE=2           # max 2% of portfolio per trade
MAX_TRADES_PER_DAY=5       # hard daily limit
```

---

## Step 3 — Start the backend + database

```bash
# From the project root
docker compose up --build -d
```

This will:
- Pull PostgreSQL 16 and Ollama images
- Build the FastAPI backend image (includes Playwright/Chromium for auto-login)
- Start all services in the background

Check that everything is running:

```bash
docker compose ps
```

Expected output:
```
NAME                   STATUS          PORTS
fasttrade-backend      running         0.0.0.0:8000->8000/tcp
fasttrade-db           running         0.0.0.0:5432->5432/tcp
fasttrade-frontend     running         0.0.0.0:3000->3000/tcp
fasttrade-ollama       running         0.0.0.0:11434->11434/tcp
```

Check backend logs:

```bash
docker compose logs -f backend
```

Look for: `Application startup complete` — the backend is ready.

---

## Step 4 — Verify the API

Open your browser: http://localhost:8000/docs

You should see the FastAPI Swagger UI. Try `GET /` — it should return `{"status": "ok"}`.

If `AUTH_ENABLED=true`, the Swagger UI will show a padlock on protected routes.

---

## Step 5 — Open the web UI

Open: http://localhost:3000

Log in with the `AUTH_USERNAME` and `AUTH_PASSWORD` you set in `.env`.

---

## Step 6 — Set up the mobile app (optional)

### Install dependencies

```bash
cd mobile
npm install
```

### Configure the API URL

Create `mobile/.env` (or edit `mobile/lib/api.ts` directly):

```
API_URL=http://YOUR_PC_LOCAL_IP:8000
```

Find your local IP:
- **Windows**: `ipconfig` → look for IPv4 under your Wi-Fi adapter
- **Mac/Linux**: `ifconfig` or `ip addr`

Your phone and PC must be on the **same Wi-Fi network**.

### Start Expo

```bash
cd mobile
npx expo start
```

Scan the QR code with **Expo Go** on your phone. You'll be prompted to log in with your app credentials.

> **Not on the same network?** Use `npx expo start --tunnel` to connect via Expo's cloud tunnel (requires Expo account).

---

## Step 7 — First-time Zerodha token

If you configured auto-login, it will run automatically at 8 AM IST every trading day.

For the **very first run**, generate a token manually:

1. Go to: `http://localhost:8000/zerodha/login` — this redirects you to Zerodha's login page
2. Log in to Zerodha
3. You'll be redirected back and the token is saved automatically
4. Or call the auto-login endpoint directly:

```bash
curl -X POST http://localhost:8000/zerodha/auto-login \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Daily Operations

| Task | How |
|------|-----|
| Start the app | `docker compose up -d` |
| Stop the app | `docker compose down` |
| View logs | `docker compose logs -f backend` |
| Restart backend only | `docker compose restart backend` |
| Update to latest code | `git pull && docker compose up --build -d` |

---

## Backup & Restore

### Create a backup

```bash
# Creates a timestamped dump in ./archives/
bash db_backup.sh
```

Or manually:

```bash
docker exec fasttrade-db pg_dump -U fasttrade fasttrade > backup_$(date +%Y%m%d).sql
```

### Restore from backup

```bash
docker exec -i fasttrade-db psql -U fasttrade fasttrade < backup_20260326.sql
```

> **Never run `docker compose down -v`** — the `-v` flag deletes the database volume permanently.

---

## Running on a VPS / Cloud Server

1. Spin up a Ubuntu 22.04 VPS (DigitalOcean, Hetzner, AWS EC2 etc.)
2. Install Docker: https://docs.docker.com/engine/install/ubuntu/
3. Clone the repo and follow steps 2–7 above
4. Open ports `8000` (API) and `3000` (web) in your firewall
5. Point your mobile app's `API_URL` to the server's public IP

**Recommended VPS spec:** 2 vCPU, 4 GB RAM, 40 GB SSD — sufficient for one user + daily candle backfill.

### Optional: Nginx reverse proxy with HTTPS

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Use [Certbot](https://certbot.eff.org/) for free Let's Encrypt SSL.

---

## Troubleshooting

### Backend fails to start

```bash
docker compose logs backend
```

Common causes:
- `.env` not found → run `cp .env.example .env` in `backend/`
- `DATABASE_URL` password mismatch with `docker-compose.yml` → ensure both use the same password
- Port 8000 already in use → change `ports: "8001:8000"` in `docker-compose.yml`

### `AUTH_SECRET_KEY` error on startup

The key `change-this-auth-secret-before-enabling` or any key shorter than 32 characters is rejected.
Generate a proper key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Auto-login not working

- Ensure `ZERODHA_TOTP_SECRET` is the **raw Base32 key** (e.g. `DTLMEIX6NYOZCEAGLQMTZKJ3TH...`), not the 6-digit code
- Check Zerodha hasn't changed their login page (Playwright may need an update)
- View logs: `docker compose logs -f backend | grep auto_login`

### Mobile can't connect

- Confirm your PC and phone are on the same Wi-Fi
- Check `API_URL` uses your PC's local IP (e.g. `http://192.168.1.10:8000`), not `localhost`
- Try `npx expo start --tunnel` as fallback

### Database issues

```bash
# Connect directly to inspect
docker exec -it fasttrade-db psql -U fasttrade -d fasttrade

# Check tables
\dt

# Exit
\q
```

---

## Security Checklist

Before going live (especially on a VPS):

- [ ] `AUTH_ENABLED=true` in `.env`
- [ ] `AUTH_PASSWORD` is a strong unique password (not `change_me_now`)
- [ ] `AUTH_SECRET_KEY` is a generated 64-char hex string
- [ ] `EXECUTION_MODE` is `PAPER_TRADING` until fully tested
- [ ] `backend/.env` is not committed to git (check `.gitignore`)
- [ ] Database password is changed from the default
- [ ] VPS firewall only opens ports 80/443 (behind Nginx) — not 8000/3000 directly
- [ ] Neon cloud sync configured as off-site backup (optional)

---

## Upgrading

```bash
git pull origin main
docker compose up --build -d
```

The backend runs database migrations automatically on startup (via `migrations.py`), so no manual SQL needed.

---

## Resetting Everything (nuclear option)

This **permanently deletes** all your data:

```bash
docker compose down -v
docker volume rm fasttrade_pgdata
docker compose up --build -d
```

Only do this if you want a completely fresh install.
