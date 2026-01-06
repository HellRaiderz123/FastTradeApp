# Frontend Setup Guide

## 📱 Overview

This project includes two separate frontend applications:
- **Web**: React + TypeScript + Vite (for desktop/browser)
- **Mobile**: React Native + Expo (for iOS/Android)

Both share the same backend API and design system.

---

## 🌐 WEB APPLICATION SETUP

### Prerequisites
- Node.js 16+ 
- npm or yarn

### Installation

```bash
cd web
npm install
```

### Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
npm run preview
```

### Project Structure

```
web/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── Sidebar.tsx     # Navigation sidebar
│   │   └── Header.tsx      # Top navigation bar
│   ├── pages/              # Page components
│   │   ├── Dashboard.tsx   # Home dashboard
│   │   ├── Strategies.tsx  # Strategy execution
│   │   ├── Positions.tsx   # Position tracking
│   │   ├── Journal.tsx     # Trade history
│   │   └── Settings.tsx    # User settings
│   ├── lib/
│   │   ├── api.ts          # API client
│   │   └── store.ts        # State management (Zustand)
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # React entry point
│   └── index.css           # Global styles
├── index.html              # HTML template
├── vite.config.ts          # Vite configuration
├── tailwind.config.ts      # Tailwind CSS config
├── tsconfig.json           # TypeScript config
└── package.json
```

### Features

✅ **Dashboard**
- Portfolio growth chart
- Real-time P&L metrics
- Win rate statistics
- Recent trades feed

✅ **Strategies**
- Strategy generator
- Signal analysis with confidence
- Risk metrics display
- Trade execution approval

✅ **Positions**
- Open positions list
- Mark-to-market P&L
- TP/SL tracking
- Quick position close

✅ **Journal**
- Trade history with filters
- Win/loss breakdown
- Performance analytics
- Export functionality

✅ **Settings**
- Trading configuration
- Risk management settings
- API integration
- Appearance preferences

### Styling

Uses **Tailwind CSS** for styling:
- Dark theme by default
- Responsive design
- Custom color palette
- Smooth animations

### State Management

**Zustand** for simple state:
- Trade state
- Signal state
- System status

### API Integration

All API calls through `lib/api.ts`:

```typescript
import { strategyAPI, executionAPI, paperAPI } from '@/lib/api';

// Run strategy
const result = await strategyAPI.runStrategy({
  underlying: 'NIFTY',
  capital: 100000,
  lots: 1,
  risk_mode: 'BALANCED'
});

// Execute trade
await executionAPI.executeIntent(intentId, idempotencyKey);

// Get positions
const positions = await paperAPI.getPositions();
```

### Deployment

#### Vercel (Recommended)

```bash
npm install -g vercel
vercel
```

#### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm ci
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

#### Self-hosted

```bash
npm run build
# Copy dist/ folder to web server
```

---

## 📱 MOBILE APPLICATION SETUP

### Prerequisites
- Node.js 16+
- Expo CLI: `npm install -g expo-cli`
- For iOS: Xcode (macOS only)
- For Android: Android Studio or Android SDK

### Installation

```bash
cd mobile
npm install
expo install
```

### Development

#### Start Expo Server
```bash
npm start
```

#### Run on Device/Emulator

```bash
# iOS (macOS only)
npm run ios

# Android
npm run android

# Web
npm run web
```

### Project Structure

```
mobile/
├── app/
│   ├── dashboard.tsx      # Dashboard screen
│   ├── strategies.tsx     # Strategies screen
│   ├── positions.tsx      # Positions screen
│   └── _layout.tsx        # Navigation layout
├── lib/
│   ├── api.ts            # API client
│   └── store.ts          # State management
├── App.tsx               # Root component
├── app.json              # Expo configuration
├── package.json
└── README.md
```

### Features

✅ **Dashboard**
- Real-time portfolio metrics
- Growth chart visualization
- Recent trades
- System status indicator

✅ **Strategies**
- Strategy execution
- Parameter input
- Result preview
- Trade execution

✅ **Positions**
- Open positions list
- Position details
- Close position button
- Risk metrics

✅ **Journal** (Coming Soon)
- Trade history
- Analytics
- Performance metrics

✅ **Settings** (Coming Soon)
- User preferences
- API configuration
- Notifications

### Network Configuration

Update `lib/api.ts` based on your environment:

```typescript
// Android Emulator
const API_BASE = 'http://10.0.2.2:8000';

// iOS Simulator
const API_BASE = 'http://localhost:8000';

// Physical Device
const API_BASE = 'http://YOUR_LOCAL_IP:8000';
```

### Building

#### Development Build
```bash
eas build -p android --profile preview
eas build -p ios --profile preview
```

#### Production Build
```bash
eas build -p android --profile production
eas build -p ios --profile production
```

#### APK (Android)
```bash
# Local build
cd android && ./gradlew assembleRelease
```

### Publishing

#### Google Play
```bash
eas submit -p android --latest
```

#### Apple App Store
```bash
eas submit -p ios --latest
```

---

## 🔗 API Integration

Both frontends connect to the same backend API.

### Base Endpoints

```
GET    /                              # Health check
POST   /strategy/option-spread/15m/run # Run strategy
POST   /intent/create                 # Create intent
POST   /execute/paper/{intent_id}     # Execute trade
POST   /exit/manual/{intent_id}       # Close position
POST   /exit/auto                     # Auto-exit triggered
POST   /paper/mtm/update              # Update position MTM
GET    /journal/strategy-runs         # Get trade history
POST   /system/enable                 # Enable trading
POST   /system/disable                # Disable trading
GET    /system/status                 # Get system status
```

### API Response Examples

#### Run Strategy
```json
{
  "strategy": "BULL_PUT",
  "approved": true,
  "reason": "Strong bullish signal",
  "signal": {
    "signal": "BULLISH",
    "confidence": 85,
    "bias": "BULLISH"
  },
  "ticket": {
    "strategy": "BULL_PUT",
    "legs": [
      { "strike": 20100, "type": "CE", "side": "SELL" },
      { "strike": 20200, "type": "CE", "side": "BUY" }
    ]
  }
}
```

---

## 🎨 Design System

### Colors
- **Primary**: Green (#10B981)
- **Secondary**: Blue (#3B82F6)
- **Danger**: Red (#EF4444)
- **Warning**: Orange (#F59E0B)
- **Dark**: #0f172a to #1f2937

### Typography
- **Font**: Inter (web), System (mobile)
- **Sizes**: 12px to 28px
- **Weights**: 400, 500, 600, 700, 900

### Components
- Glass-morphism cards (`.card-glass`)
- Gradient buttons (`.btn-primary`, `.btn-secondary`)
- Smooth transitions
- Dark mode optimized

---

## 📦 Shared Libraries

Both apps use:
- **axios**: HTTP client
- **zustand**: State management
- **date-fns**: Date utilities

### Shared API Client

Code is duplicated between web and mobile for simplicity. To share:

```typescript
// Create common folder
packages/
├── api-client/
│   └── src/
│       ├── api.ts
│       └── store.ts
```

Then import in both projects.

---

## 🚀 Deployment

### Web

**Production Checklist:**
- [ ] Build: `npm run build`
- [ ] Test build: `npm run preview`
- [ ] Set API_BASE to production URL
- [ ] Deploy to Vercel/Netlify/Server
- [ ] Enable HTTPS
- [ ] Setup monitoring
- [ ] Configure CORS on backend

### Mobile

**Production Checklist:**
- [ ] Update app version in `app.json`
- [ ] Set API_BASE to production URL
- [ ] Build production APK/IPA
- [ ] Test on physical device
- [ ] Sign APK/IPA
- [ ] Submit to app stores
- [ ] Setup analytics
- [ ] Setup crash reporting

---

## 🔒 Security

### API Keys
Never commit API keys to repository:
```bash
# Create .env file
VITE_API_BASE=http://localhost:8000

# Web .env
REACT_APP_API_BASE=http://localhost:8000

# Mobile (use environment variables or Expo secrets)
```

### CORS
Configure backend CORS for frontend domains:

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Authentication (Coming Soon)
Add JWT authentication for user accounts:
- Login endpoint
- Token refresh
- Protected routes

---

## 🐛 Troubleshooting

### Web

**Port already in use**
```bash
# Find and kill process on port 3000
# macOS/Linux
lsof -ti:3000 | xargs kill -9

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

**Module not found**
```bash
rm -rf node_modules package-lock.json
npm install
```

### Mobile

**Android emulator can't connect to backend**
- Use `10.0.2.2` instead of `localhost`
- Check firewall allows port 8000
- Restart emulator

**iOS simulator networking**
- Ensure backend is running
- Use `localhost:8000`
- Check System Preferences > Network

**Expo go crashes**
- Clear cache: `expo cache --clear`
- Rebuild: `npm install --force`
- Check Node version: `node --version` (should be 16+)

---

## 📚 Resources

- [Vite Documentation](https://vitejs.dev/)
- [React Documentation](https://react.dev/)
- [React Native Documentation](https://reactnative.dev/)
- [Expo Documentation](https://docs.expo.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Zustand Documentation](https://github.com/pmndrs/zustand)

---

## 📞 Support

For issues:
1. Check troubleshooting section
2. Review console errors
3. Check backend health: `GET http://localhost:8000/`
4. Verify API endpoint configuration

---

## 📝 Next Steps

1. Install dependencies for both web and mobile
2. Start backend: `cd backend && uvicorn app.main:app --reload`
3. Start web: `cd web && npm run dev`
4. Start mobile: `cd mobile && npm start`
5. Run paper trading tests
6. Deploy to production

---

**Last Updated:** January 5, 2026  
**Version:** 1.0.0
