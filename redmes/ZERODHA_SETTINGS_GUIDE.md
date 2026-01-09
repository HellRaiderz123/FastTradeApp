# Zerodha API Settings & Access Token Management

## Overview

The Settings module provides a user-friendly interface for managing Zerodha API credentials and access tokens directly from the mobile app. This eliminates the need to manually edit `.env` files.

## Features

- ✅ **API Credentials Management** - Save and update Zerodha API Key and Secret
- ✅ **Access Token Management** - Manually set access tokens obtained from Zerodha
- ✅ **Execution Mode Selection** - Switch between LIVE, DRY_RUN, and PAPER_TRADING modes
- ✅ **Connection Status** - Real-time display of configuration status
- ✅ **Environment Persistence** - Changes are saved to `.env` file automatically

## Backend API Endpoints

### 1. Get Settings Status
```
GET /settings/zerodha
```
Returns current configuration status:
```json
{
  "api_key_set": true,
  "access_token_set": true,
  "execution_mode": "ZERODHA_DRY_RUN"
}
```

### 2. Save API Credentials
```
POST /settings/zerodha/credentials
```
Request body:
```json
{
  "api_key": "your-api-key",
  "api_secret": "your-api-secret"
}
```

### 3. Save Access Token
```
POST /settings/zerodha/token
```
Request body:
```json
{
  "access_token": "your-access-token"
}
```

### 4. Set Execution Mode
```
POST /settings/execution-mode?mode=ZERODHA_LIVE
```
Valid modes:
- `ZERODHA_LIVE` - Execute real trades
- `ZERODHA_DRY_RUN` - Simulate trades without execution
- `PAPER_TRADING` - Paper trading mode

### 5. Generate Access Token (Future)
```
POST /settings/zerodha/generate-token
```
*Note: Currently requires manual token generation via Zerodha web interface*

## How to Use

### Step 1: Get Your API Credentials

1. Log in to your Zerodha account at https://kite.zerodha.com
2. Go to **Settings** → **API Consultants**
3. If you don't have an API application, create one
4. Copy your **API Key** and **API Secret**

### Step 2: Configure in FastTradeApp

1. Open the **Settings** tab in the FastTradeApp mobile interface
2. Navigate to **Zerodha API Credentials**
3. Enter your API Key and API Secret
4. Click **Save Credentials**

### Step 3: Generate Access Token

1. Visit https://kite.zerodha.com and log in
2. Your access token will be active after login
3. Alternatively, use Zerodha's token generation flow
4. Copy the access token

### Step 4: Save Access Token

1. In the **Settings** tab, navigate to **Access Token**
2. Paste your access token
3. Click **Save Token**

### Step 5: Choose Execution Mode

1. In the **Settings** tab, navigate to **Execution Mode**
2. Select your preferred mode:
   - **ZERODHA_DRY_RUN** (recommended for testing)
   - **ZERODHA_LIVE** (for live trading)
   - **PAPER_TRADING** (for simulated trading)

## File Modifications

### Backend Changes

**File: `backend/app/api/routes/settings.py`** (NEW)
- Complete settings management module
- Zerodha credentials and token handling
- Execution mode configuration
- Environment file persistence

**File: `backend/app/main.py`**
- Imports settings router
- Registers settings endpoints at `/settings/*`

### Frontend Changes

**File: `mobile/app/settings.tsx`** (NEW)
- Settings UI component
- Zerodha credentials form
- Access token input
- Execution mode selector
- Connection status display

**File: `mobile/lib/api.ts`**
- Added `settingsAPI` object with all settings endpoints

**File: `mobile/App.tsx`**
- Imports and uses actual SettingsScreen component

## Environment Variables

The following environment variables are managed through the Settings interface:

```env
ZERODHA_API_KEY=your-api-key
ZERODHA_API_SECRET=your-api-secret
ZERODHA_ACCESS_TOKEN=your-access-token
EXECUTION_MODE=ZERODHA_DRY_RUN
```

## Security Notes

⚠️ **Important Security Considerations:**

1. **API Secret** - Never share your API secret with anyone
2. **Access Token** - Keep your access token confidential
3. **Environment File** - The `.env` file contains sensitive data; never commit it to git
4. **Production** - Consider using environment variables from a secure vault in production

## Troubleshooting

### "Credentials saved but connection fails"
- Verify API Key and Secret are correct
- Check if your Zerodha account has API access enabled
- Ensure the access token is fresh (not expired)

### "Invalid execution mode"
- Valid modes are: `ZERODHA_LIVE`, `ZERODHA_DRY_RUN`, `PAPER_TRADING`
- Check for spelling and case sensitivity

### "Token generation not implemented"
- Token generation requires OAuth flow with user interaction
- For now, manually obtain the token from Zerodha web interface and save it

## API Request Examples

### Using curl to test endpoints:

```bash
# Get settings status
curl http://localhost:8000/settings/zerodha

# Save credentials
curl -X POST http://localhost:8000/settings/zerodha/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-key",
    "api_secret": "your-secret"
  }'

# Save access token
curl -X POST http://localhost:8000/settings/zerodha/token \
  -H "Content-Type: application/json" \
  -d '{"access_token": "your-token"}'

# Set execution mode
curl -X POST "http://localhost:8000/settings/execution-mode?mode=ZERODHA_DRY_RUN"
```

## Next Steps

1. ✅ Settings module created with full API
2. ✅ Mobile UI for credential management
3. ✅ Environment persistence
4. 🔄 Future: OAuth token generation flow
5. 🔄 Future: Settings encryption for production
6. 🔄 Future: Multi-account support

## Testing

To test the settings functionality:

```bash
# Terminal 1: Start the backend
cd backend
python -m uvicorn app.main:app --reload

# Terminal 2: Test the endpoints
# See "API Request Examples" section above
```

The settings will persist in your `.env` file even after restarting the application.
