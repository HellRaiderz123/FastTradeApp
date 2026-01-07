# Phase 5 - Production Features Setup Guide

## 🚀 Features Implemented

### 1. **Notification System** ✅
- ✅ In-app notifications (stored in database)
- ✅ Gmail integration for critical alerts
- ✅ Multi-priority system (LOW, MEDIUM, HIGH, CRITICAL)
- ✅ Notification types:
  - Trade executed/failed
  - TP/SL/Trailing SL hits
  - Daily P&L threshold (±5%)
  - System errors
  - Margin warnings
  - Strategy enable/disable

### 2. **WebSocket Real-Time Updates** ✅
- ✅ Live MTM updates (every 5s)
- ✅ Position updates
- ✅ Trade executions
- ✅ System status (every 10s)
- ✅ Connection management

### 3. **Order Status Monitoring** ✅
- ✅ Order lifecycle tracking
- ✅ Partial fill handling
- ✅ Retry logic (3 attempts)
- ✅ Position reconciliation with broker

### 4. **Health Monitoring** ✅
- ✅ Heartbeat endpoint
- ✅ Database health checks
- ✅ Candle freshness monitoring
- ✅ System resource tracking (CPU, memory, disk)
- ✅ API performance tracking

### 5. **Enhanced Logging** ✅
- ✅ Structured JSON logging
- ✅ Request ID tracking
- ✅ Performance logging
- ✅ Error aggregation
- ✅ Colored console output (dev)

---

## 📦 Installation

### 1. Install New Dependencies

```bash
cd backend
pip install psutil==5.9.8 websockets==12.0
```

### 2. Setup Gmail for Notifications

Create a Gmail App Password:
1. Go to Google Account settings
2. Security → 2-Step Verification → App passwords
3. Generate app password for "Mail"

Add to `.env`:
```env
# Gmail Notifications
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ALERT_EMAIL=your-email@gmail.com

# Logging
LOG_LEVEL=INFO
JSON_LOGS=false
```

### 3. Create Database Tables

```bash
# The notification table will be auto-created on startup
python -c "from app.db.session import engine; from app.db.models_notification import Notification; Notification.metadata.create_all(engine)"
```

---

## 🔌 API Endpoints

### Notifications

```bash
# Get unread notifications
GET /notifications/unread?limit=50

# Get all notifications
GET /notifications/all?limit=100

# Mark as read
POST /notifications/mark-read
{
  "notification_ids": [1, 2, 3]
}

# Mark all as read
POST /notifications/mark-all-read

# Get unread count
GET /notifications/unread-count

# Clear old notifications
DELETE /notifications/clear-old?days=30
```

### WebSocket

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/live');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'mtm_update':
      // Update positions with latest MTM
      break;
    case 'position_update':
      // Handle position change
      break;
    case 'trade_execution':
      // Show trade notification
      break;
    case 'notification':
      // Show in-app notification
      break;
    case 'system_status':
      // Update system status badge
      break;
  }
};

// Get connection count
GET /ws/connections
```

### Health Monitoring

```bash
# Simple health check
GET /health/

# Heartbeat
GET /health/heartbeat

# Full health status
GET /health/full

# Database health
GET /health/database

# Candle freshness
GET /health/candles

# System resources
GET /health/resources

# API performance
GET /health/performance
GET /health/performance/strategies/run/single
```

---

## 💻 Usage Examples

### 1. Send Notification After Trade

```python
from app.services.notifications import get_notification_service
from app.db.session import SessionLocal

db = SessionLocal()
service = get_notification_service(db)

# Trade executed
service.notify_trade_executed(
    strategy_name="NIFTY Bull Put",
    underlying="NIFTY",
    trade_details={
        "entry_credit": 500.50,
        "legs": [...]
    }
)

# TP hit
service.notify_tp_hit("NIFTY Bull Put", pnl=450.0, pnl_pct=2.5)

# System error
service.notify_system_error(
    error_type="ZerodhaAPIError",
    error_message="Connection timeout",
    component="ExecutionEngine"
)

db.close()
```

### 2. Monitor Order Status

```python
from app.services.order_monitor import OrderMonitor
from app.core.broker.zerodha.client import get_kite_client

kite = get_kite_client()
monitor = OrderMonitor(kite, db)

# Place order with monitoring
result = monitor.place_order_with_monitoring(
    order_params={
        "exchange": "NFO",
        "tradingsymbol": "NIFTY26FEB26000PE",
        "transaction_type": "SELL",
        "quantity": 65,
        "order_type": "MARKET"
    },
    intent_id="intent_123",
    retry_on_reject=True
)

# Check order status
status = monitor.get_order_status(order_id="240107000123456")

# Reconcile positions
reconciliation = monitor.reconcile_positions()
```

### 3. Broadcast WebSocket Update

```python
from app.services.websocket import broadcast_trade_execution

# After trade execution
await broadcast_trade_execution({
    "strategy": "NIFTY Bull Put",
    "entry_credit": 500.50,
    "timestamp": "2026-01-07T10:30:00"
})
```

### 4. Check System Health

```python
from app.services.health_monitor import HealthMonitor

monitor = HealthMonitor(db)

# Get full health
health = monitor.get_full_health_status()
print(health)

# Check specific component
db_health = monitor.check_database()
candles = monitor.check_candle_freshness()
```

---

## 🔧 Configuration

### Environment Variables

```env
# Notifications
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
ALERT_EMAIL=alerts@yourdomain.com

# Logging
LOG_LEVEL=INFO           # DEBUG, INFO, WARNING, ERROR
JSON_LOGS=false          # true for production (structured logs)

# Monitoring
HEALTH_CHECK_INTERVAL=10  # seconds
MTM_UPDATE_INTERVAL=5     # seconds
```

### Notification Triggers

The system automatically sends notifications for:

| Trigger | Priority | Channels |
|---------|----------|----------|
| Trade Executed | MEDIUM | In-app |
| Trade Failed | HIGH | In-app + Email |
| TP Hit | MEDIUM | In-app |
| SL Hit | HIGH | In-app + Email |
| Daily P&L ±5% | HIGH | In-app + Email |
| System Error | CRITICAL | In-app + Email |
| Margin Warning | CRITICAL | In-app + Email |

---

## 🧪 Testing

### 1. Test Notifications

```bash
# Start backend
uvicorn app.main:app --reload

# Test endpoints
curl http://localhost:8000/notifications/unread
```

### 2. Test WebSocket

```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8000/ws/live');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### 3. Test Health Checks

```bash
curl http://localhost:8000/health/full | jq
```

---

## 📊 Monitoring in Production

### 1. Log Files

Logs are stored in `backend/logs/app.log` with rotation (10MB per file, 5 backups)

### 2. Error Tracking

```python
from app.core.logging_config import error_tracker

# Get error summary
summary = error_tracker.get_error_summary()
```

### 3. Performance Monitoring

```python
from app.services.health_monitor import performance_tracker

# Get all API stats
stats = performance_tracker.get_all_stats()
```

---

## 🚀 Next Steps

1. ✅ Install dependencies
2. ✅ Configure Gmail
3. ✅ Test notification endpoints
4. ✅ Connect WebSocket from frontend
5. ✅ Monitor logs and health checks
6. 🔄 Integrate notifications into execution flow
7. 🔄 Add frontend notification bell icon
8. 🔄 Create notification preferences UI

---

## 🐛 Troubleshooting

### Gmail Not Sending

- Verify `GMAIL_APP_PASSWORD` is correct (16-char, no spaces)
- Check 2-Step Verification is enabled
- Try from a different network (not blocked by firewall)

### WebSocket Not Connecting

- Check CORS settings in main.py
- Verify WebSocket URL (`ws://` not `wss://`)
- Check firewall/proxy settings

### Notifications Not Appearing

- Check database table created: `SELECT * FROM notifications;`
- Verify notification service is initialized
- Check logs for errors

---

## 📚 Documentation

- Notification Service: `backend/app/services/notifications.py`
- WebSocket Manager: `backend/app/services/websocket.py`
- Order Monitor: `backend/app/services/order_monitor.py`
- Health Monitor: `backend/app/services/health_monitor.py`
- Logging Config: `backend/app/core/logging_config.py`

---

**Status**: ✅ Phase 5 Complete - Ready for Integration Testing
