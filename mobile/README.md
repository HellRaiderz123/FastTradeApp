# FastTrade Mobile

React Native mobile application for FastTrade algorithmic trading platform.

## Installation

### Prerequisites
- Node.js 16+
- Expo CLI: `npm install -g expo-cli`
- iOS: Xcode (for development)
- Android: Android Studio (for development)

### Setup

```bash
cd mobile
npm install
```

### Development

```bash
# iOS
npm run ios

# Android
npm run android

# Web
npm run web
```

## Architecture

### Screens
- **Dashboard** - Real-time portfolio metrics and performance
- **Strategies** - Strategy execution and analysis
- **Positions** - Open positions and management
- **Journal** - Trade history and analytics (coming soon)
- **Settings** - Configuration and preferences (coming soon)

### Components
- Tab navigation for easy switching
- Real-time data updates
- Offline-first data caching
- Touch-optimized UI

## API Integration

All API calls are handled through `lib/api.ts`:
- Strategy generation
- Position management
- Trade execution
- System control

## Backend Connection

Update the API endpoint in `lib/api.ts`:

```typescript
// For Android emulator
const API_BASE = 'http://10.0.2.2:8000';

// For iOS simulator
const API_BASE = 'http://localhost:8000';

// For physical device
const API_BASE = 'http://YOUR_IP:8000';
```

## State Management

Uses Zustand for lightweight state management:
- Trade store
- System status
- User preferences

## Coming Soon

- [ ] Push notifications
- [ ] Biometric authentication
- [ ] Offline support
- [ ] Advanced charting
- [ ] Community features
- [ ] Voice commands

## Troubleshooting

### Android Emulator Network
If backend connection fails:
1. Ensure backend is running on `8000`
2. Check firewall settings
3. Use `10.0.2.2` instead of `localhost`

### iOS Simulator Network
For local development:
```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# In mobile app, use localhost:8000
```

## Building for Production

```bash
# Build APK (Android)
eas build -p android

# Build IPA (iOS)
eas build -p ios
```

## Publishing

```bash
eas submit -p android
eas submit -p ios
```
