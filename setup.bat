@echo off
REM FastTrade Full Stack Setup Script for Windows

echo 🚀 FastTrade Setup Script
echo =========================
echo.

REM Check Node.js
echo 📋 Checking prerequisites...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install Node.js 16+
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo ✓ Node.js %NODE_VERSION%

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ npm not found
    exit /b 1
)

for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo ✓ npm %NPM_VERSION%

echo.
echo 📦 Installing dependencies...
echo.

REM Web Setup
echo 🌐 Setting up Web application...
cd web
call npm install
if %errorlevel% neq 0 (
    echo ❌ Web setup failed
    cd ..
    exit /b 1
)
echo ✓ Web dependencies installed
cd ..

echo.

REM Mobile Setup
echo 📱 Setting up Mobile application...
cd mobile
call npm install
if %errorlevel% neq 0 (
    echo ❌ Mobile setup failed
    cd ..
    exit /b 1
)
echo ✓ Mobile dependencies installed
cd ..

echo.
echo ✅ Setup complete!
echo.
echo 📝 Next Steps:
echo ==============
echo.
echo 1. Backend:
echo    cd backend
echo    python -m venv venv
echo    .\venv\Scripts\activate
echo    pip install -r requirements.txt
echo    uvicorn app.main:app --reload
echo.
echo 2. Web (new terminal):
echo    cd web
echo    npm run dev
echo    → http://localhost:3000
echo.
echo 3. Mobile (new terminal):
echo    cd mobile
echo    npm start
echo    → Scan QR code with Expo Go
echo.
echo 📖 Read FRONTEND_SETUP.md for detailed instructions
echo.
pause
