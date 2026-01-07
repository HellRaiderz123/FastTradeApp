# ⚙️ Quick Settings Setup

## What's New

You now have a **Settings page** in the mobile app to manage Zerodha API credentials without editing files!

## Quick Start (5 minutes)

### 1️⃣ Get Your API Credentials
- Go to https://kite.zerodha.com
- Settings → API Consultants
- Copy your **API Key** and **API Secret**

### 2️⃣ Open App Settings
- Tap the **Settings ⚙️** tab at the bottom
- Scroll to **Zerodha API Credentials**

### 3️⃣ Enter Credentials
- Paste your API Key
- Paste your API Secret
- Tap **Save Credentials** (green button)

### 4️⃣ Get Access Token
- Log in to Zerodha web (https://kite.zerodha.com)
- Copy your access token (if available, or generate one)

### 5️⃣ Save Token
- In Settings → **Access Token** section
- Paste the token
- Tap **Save Token** (blue button)

### 6️⃣ Choose Mode
- In Settings → **Execution Mode** section
- Select **ZERODHA_DRY_RUN** for testing
- Or **ZERODHA_LIVE** for real trading

## What Changed

| Component | What's New |
|-----------|-----------|
| **Backend** | `backend/app/api/routes/settings.py` - New settings API |
| **Frontend** | `mobile/app/settings.tsx` - New Settings screen |
| **API Helper** | `mobile/lib/api.ts` - Added settingsAPI functions |
| **Main App** | `mobile/App.tsx` - Uses real Settings component |

## Endpoints (for developers)

```
GET    /settings/zerodha                    → Get status
POST   /settings/zerodha/credentials        → Save API key/secret
POST   /settings/zerodha/token              → Save access token
POST   /settings/execution-mode?mode=...    → Change mode
```

## Status Indicators

| Indicator | Meaning |
|-----------|---------|
| ✓ Configured | Setting is properly saved |
| ✗ Not Set | Setting needs to be configured |

## Execution Modes

| Mode | Purpose |
|------|---------|
| **ZERODHA_DRY_RUN** | ✅ Recommended for testing (no real trades) |
| **ZERODHA_LIVE** | ⚠️ Executes real trades (use with caution) |
| **PAPER_TRADING** | 📊 Simulated trading for backtesting |

## Common Issues

❌ **"Error saving credentials"**
- Verify API Key and Secret are not empty
- Check for typos
- Ensure they're copied completely

❌ **"Connection failed after saving"**
- Log in to Zerodha web again to refresh token
- Verify your account has API access enabled
- Re-enter the access token

❌ **"Token has expired"**
- Log in to Zerodha web again
- Copy and save the new access token in Settings

## File Storage

All settings are saved to: `backend/.env`

Example:
```
ZERODHA_API_KEY=el4pv3dwria188j9
ZERODHA_API_SECRET=your-secret-here
ZERODHA_ACCESS_TOKEN=token-here
EXECUTION_MODE=ZERODHA_DRY_RUN
```

## Security Reminder

🔐 Keep these private:
- API Secret
- Access Token
- Never share your `.env` file
- Never commit `.env` to git

## Need Help?

See the full guide: `ZERODHA_SETTINGS_GUIDE.md`
