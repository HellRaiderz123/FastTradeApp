# Phase 5 - Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Install Dependencies (1 min)
```powershell
cd backend
pip install psutil websockets
```

### Step 2: Configure Gmail (2 min)
```powershell
# Add to backend/.env
echo "GMAIL_USER=your-email@gmail.com" >> .env
echo "GMAIL_APP_PASSWORD=your-app-password" >> .env
echo "ALERT_EMAIL=your-email@gmail.com" >> .env
```

**Get Gmail App Password:**
1. Google Account → Security → 2-Step Verification
2. App passwords → Generate for "Mail"
3. Copy 16-character password

### Step 3: Create Database Table (30 sec)
```powershell
cd backend
python migrate_notifications.py
```

### Step 4: Test Everything (1 min)
```powershell
# Test Phase 5 features
python test_phase5_complete.py
```

Expected output:
```
✅ PASS - Database Tables
✅ PASS - Notifications
✅ PASS - Health Monitoring
✅ PASS - WebSocket
✅ PASS - Logging
✅ PASS - API Endpoints

ALL TESTS PASSED! Phase 5 is ready for production! 🚀
```

### Step 5: Start Server (30 sec)
```powershell
uvicorn app.main:app --reload
```

Server will start with:
```
✅ Database tables initialized
✅ Schedulers started for live data updates
✅ WebSocket background tasks started
✅ All routers registered (including Phase 5 features)
```

---

## 🎯 What You Get

### 1. Real-Time Notifications
- Trade executed/failed alerts
- TP/SL hit notifications
- Daily P&L threshold alerts (±5%)
- System error notifications
- Margin warnings

### 2. Live Dashboard Updates
- MTM updates every 5 seconds
- Position changes in real-time
- System status updates
- No page refresh needed

### 3. System Monitoring
- Health check endpoints
- API performance tracking
- Resource usage monitoring
- Candle freshness checks

### 4. Production Logging
- Structured JSON logs
- Request ID tracking
- Performance metrics
- Error aggregation

---

## 📱 Frontend Integration

### Add Notification Bell
In `web/src/components/Header.tsx`:
```tsx
import { NotificationBell } from './NotificationBell';

// In render:
<NotificationBell />
```

### Connect WebSocket
```tsx
const ws = new WebSocket('ws://localhost:8000/ws/live');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'mtm_update':
      updatePositions(data.data);
      break;
    case 'notification':
      showNotification(data.data);
      break;
  }
};
```

---

## ✅ Testing Checklist

- [ ] Install dependencies
- [ ] Configure Gmail
- [ ] Run migration script
- [ ] Run test suite
- [ ] Start server
- [ ] Check notifications at `/notifications/unread`
- [ ] Connect to WebSocket at `/ws/live`
- [ ] Check health at `/health/full`
- [ ] View logs in `backend/logs/app.log`

---

## 🔗 Quick Links

### API Documentation
- Swagger UI: http://localhost:8000/docs
- Health Check: http://localhost:8000/health/
- Notifications: http://localhost:8000/notifications/unread

### Test Endpoints
```bash
# Get unread notifications
curl http://localhost:8000/notifications/unread

# Health check
curl http://localhost:8000/health/full | jq

# WebSocket connections
curl http://localhost:8000/ws/connections
```

---

## 🆘 Troubleshooting

### "Gmail not configured"
→ Add GMAIL_USER and GMAIL_APP_PASSWORD to .env

### "Table doesn't exist"
→ Run: `python migrate_notifications.py`

### "Module not found: psutil"
→ Run: `pip install psutil websockets`

### "WebSocket won't connect"
→ Use `ws://` not `wss://` for localhost

---

## 🎓 Next Steps

1. ✅ Test all features locally
2. 🔄 Integrate notifications into your execution flow
3. 🔄 Add WebSocket to frontend dashboard
4. 🔄 Monitor in staging environment
5. 🚀 Deploy to production!

---

**Documentation:**
- Full Guide: `PHASE_5_SETUP_GUIDE.md`
- Complete Report: `PHASE_5_COMPLETE.md`
- Examples: `backend/examples/notification_integration_example.py`

**Status**: ✅ READY FOR PRODUCTION
