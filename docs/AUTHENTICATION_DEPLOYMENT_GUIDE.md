# Authentication Implementation - Deployment Guide

## Overview
FastTradeApp now has a complete JWT-based authentication system using HMAC-SHA256 signed bearer tokens. The system is **currently disabled** by default to prevent breaking existing workflows until you're ready to enable it.

## Implementation Summary

### Backend Components
1. **Core Auth Module** (`backend/app/core/auth.py`)
   - HMAC token generation and validation
   - Password verification using environment credentials
   - FastAPI dependency for protected routes

2. **Auth Endpoints** (`backend/app/api/routes/auth.py`)
   - `POST /auth/login` - Username/password authentication, returns JWT token
   - `GET /auth/me` - Get current user info (requires valid token)

3. **Protected Routes** (`backend/app/main.py`)
   - 11 trading-critical router groups now require authentication:
     - intent, execute, account, strategies, execution_v2
     - settings, paper_mtm, exit, auto_exit, system
     - zerodha_broker, auto_trader

### Frontend Components
1. **Login Page** (`web/src/pages/Login.tsx`)
   - Username/password form
   - Token storage on successful authentication
   - Error handling and validation

2. **Protected Route Wrapper** (`web/src/components/ProtectedRoute.tsx`)
   - Checks for valid token before rendering protected pages
   - Redirects to `/login` if unauthenticated
   - Validates token with backend on mount

3. **Logout Functionality** (`web/src/components/Header.tsx`)
   - User menu dropdown with logout button
   - Clears token and redirects to login page

4. **API Client Integration** (`web/src/lib/api.ts`)
   - Token storage in localStorage
   - Automatic Bearer token injection in all API requests
   - Auth API methods (login, logout, me)

## Enabling Authentication

### Step 1: Configure Environment Variables

Edit `backend/.env`:

```env
# Enable authentication (currently set to 'false')
AUTH_ENABLED='true'

# Set your credentials (CHANGE THESE!)
AUTH_USERNAME='admin'
AUTH_PASSWORD='your_secure_password_here'

# Generate a secure random secret key
# On Linux/Mac: python -c "import secrets; print(secrets.token_urlsafe(32))"
# On Windows: python -c "import secrets; print(secrets.token_urlsafe(32))"
AUTH_SECRET_KEY='REPLACE_WITH_RANDOM_32_BYTE_STRING'

# Token expiration (in minutes)
AUTH_TOKEN_EXPIRE_MINUTES=480
```

**CRITICAL SECURITY STEPS:**
1. Change `AUTH_PASSWORD` from `'change_me_now'` to a strong password
2. Generate a cryptographically random `AUTH_SECRET_KEY`:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. Update `AUTH_USERNAME` if you prefer a different username (default is 'admin')

### Step 2: Restart Backend Server

```powershell
# Stop current backend server (Ctrl+C)
# Restart backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Restart Frontend Server

```powershell
# Stop current frontend server (Ctrl+C)
# Restart frontend
cd web
npm run dev
```

## Testing Authentication

### Test 1: Verify Login Required
1. Clear browser localStorage: Open DevTools → Application → Local Storage → Clear All
2. Navigate to `http://localhost:5173/`
3. **Expected:** You should be redirected to `/login` page

### Test 2: Test Login Flow
1. Enter username: `admin` (or whatever you set in AUTH_USERNAME)
2. Enter password: (the value you set in AUTH_PASSWORD)
3. Click "Sign In"
4. **Expected:** You should be redirected to the Terminal dashboard

### Test 3: Verify Protected Routes
1. After successful login, navigate to different pages:
   - `/dashboard`
   - `/strategies`
   - `/positions`
   - `/settings`
2. **Expected:** All pages should load without redirecting to login

### Test 4: Verify Token Persistence
1. After login, refresh the page
2. **Expected:** You should remain logged in (token stored in localStorage)

### Test 5: Verify Logout
1. Click on user menu (top right, "Tarun" with avatar)
2. Click "Logout"
3. **Expected:** You should be redirected to `/login` and token should be cleared

### Test 6: Test Invalid Credentials
1. Go to `/login`
2. Enter wrong username or password
3. **Expected:** Error message "Invalid username or password"

### Test 7: Test Backend API Directly

#### Without Token (Should Fail):
```powershell
# Test protected endpoint without token
curl http://localhost:8000/strategies/current

# Expected: {"detail":"Not authenticated"}
```

#### With Token (Should Work):
```powershell
# Get token
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/auth/login" -Headers @{"Content-Type"="application/x-www-form-urlencoded"} -Body "username=admin&password=your_password_here"
$token = $response.access_token

# Test protected endpoint with token
$headers = @{"Authorization" = "Bearer $token"}
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/strategies/current" -Headers $headers
```

## Architecture Details

### Token Flow
1. User submits credentials to `POST /auth/login`
2. Backend verifies credentials, generates HMAC-signed JWT token
3. Frontend stores token in localStorage
4. All subsequent API requests include `Authorization: Bearer <token>` header
5. Backend validates token signature and expiration on each request

### Token Structure
```json
{
  "sub": "admin",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### Security Features
- HMAC-SHA256 signature prevents token tampering
- Token expiration (default 8 hours)
- No password storage in tokens
- Password validation on every login
- Automatic token validation on protected routes

## Troubleshooting

### Issue: "Invalid username or password" on correct credentials
**Solution:** Check `backend/.env` for correct `AUTH_USERNAME` and `AUTH_PASSWORD`

### Issue: Backend returns "Not authenticated" even with token
**Solution:** 
- Verify `AUTH_ENABLED='true'` in `.env`
- Check backend logs for token validation errors
- Verify `AUTH_SECRET_KEY` is set and hasn't changed since token was issued

### Issue: Frontend keeps redirecting to login
**Solution:**
- Check browser console for API errors
- Verify backend is running on `http://localhost:8000`
- Check if token is stored in localStorage (DevTools → Application → Local Storage)

### Issue: Token expired immediately
**Solution:** Check `AUTH_TOKEN_EXPIRE_MINUTES` in `.env` (default is 480 minutes = 8 hours)

## Disabling Authentication

To disable authentication (revert to open access):

1. Edit `backend/.env`:
   ```env
   AUTH_ENABLED='false'
   ```

2. Restart backend server

All routes will be accessible without authentication.

## Multi-User Support (Optional)

The current implementation supports single-user authentication. To add multiple users:

### Option 1: Database-backed Users
1. Create `users` table in SQLite with columns: id, username, hashed_password
2. Modify `backend/app/core/auth.py` to query database instead of env variables
3. Hash passwords using bcrypt or argon2
4. Add user registration endpoint

### Option 2: Environment Variable Multiple Users
1. Store multiple users in `.env`:
   ```env
   AUTH_USERS='{"admin":"password1","trader":"password2"}'
   ```
2. Parse JSON in `verify_login_credentials()` function
3. Loop through users to validate credentials

## Next Steps After Authentication

With authentication enabled, consider these production safety features:

1. **LTP Zero-Guard** - Block orders when last traded price <= 0
2. **Emergency Close All** - Panic button to flatten all positions
3. **Rate Limiting** - Prevent API abuse
4. **Audit Logging** - Log all trade executions with user info
5. **Role-Based Access Control** - Admin vs Trader permissions

## Files Modified

### Backend
- `backend/app/core/auth.py` (NEW)
- `backend/app/api/routes/auth.py` (NEW)
- `backend/app/main.py` (modified - added auth router and dependencies)
- `backend/.env` (modified - added AUTH_* variables)

### Frontend
- `web/src/pages/Login.tsx` (NEW)
- `web/src/components/ProtectedRoute.tsx` (NEW)
- `web/src/components/Header.tsx` (modified - added logout dropdown)
- `web/src/App.tsx` (modified - added login route and ProtectedRoute wrapper)
- `web/src/lib/api.ts` (modified - added token storage and interceptor)

---

**Status:** Authentication system is fully implemented and tested. Currently DISABLED by default (`AUTH_ENABLED='false'`). Follow steps above to enable.
