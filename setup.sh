#!/bin/bash

# FastTrade Full Stack Setup Script

echo "🚀 FastTrade Setup Script"
echo "========================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Node.js
echo "📋 Checking prerequisites..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Please install Node.js 16+${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Node.js $(node --version)${NC}"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ npm $(npm --version)${NC}"

echo ""
echo "📦 Installing dependencies..."
echo ""

# Web Setup
echo "🌐 Setting up Web application..."
cd web
npm install
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Web dependencies installed${NC}"
else
    echo -e "${RED}❌ Web setup failed${NC}"
    exit 1
fi
cd ..

echo ""

# Mobile Setup
echo "📱 Setting up Mobile application..."
cd mobile
npm install
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Mobile dependencies installed${NC}"
else
    echo -e "${RED}❌ Mobile setup failed${NC}"
    exit 1
fi
cd ..

# Backend Setup
echo ""
echo "⚙️  Backend setup..."
if [ -d "backend" ]; then
    echo "Backend folder found."
    echo "Note: Configure Python environment manually:"
    echo "  cd backend"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate  # macOS/Linux"
    echo "  .\\venv\\Scripts\\activate  # Windows"
    echo "  pip install -r requirements.txt"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📝 Next Steps:"
echo "=============="
echo ""
echo "1. Backend:"
echo "   cd backend"
echo "   uvicorn app.main:app --reload"
echo ""
echo "2. Web (new terminal):"
echo "   cd web"
echo "   npm run dev"
echo "   → http://localhost:3000"
echo ""
echo "3. Mobile (new terminal):"
echo "   cd mobile"
echo "   npm start"
echo "   → Scan QR code with Expo Go"
echo ""
echo "📖 Read FRONTEND_SETUP.md for detailed instructions"
echo ""
