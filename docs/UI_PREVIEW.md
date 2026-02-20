# 🎨 UI PREVIEW & COMPONENTS

## 🌐 WEB APPLICATION SCREENSHOTS (Text Layout)

### Dashboard
```
┌─────────────────────────────────────────────────────────────────┐
│ FastTrade Pro                                      🟢 TRADING ON │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Capital: ₹100,000    P&L: ₹3,200    Trades: 5    Win: 80%    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
│                                                                   │
│  Portfolio Growth Chart                                          │
│  ╔════════════════════════════════════════════════╗             │
│  ║          ╱╲    ╱╲                             ║             │
│  ║        ╱    ╲╱  ╲╱╲                          ║             │
│  ║       ╱            ╲╱╲                        ║             │
│  ║                                               ║             │
│  ╚════════════════════════════════════════════════╝             │
│                                                                   │
│  Quick Stats:          Recent Trades:                           │
│  • Avg Win: ₹2,400    • BULL_PUT NIFTY +₹2,100                │
│  • Avg Loss: ₹1,200   • BEAR_CALL NIFTY +₹1,500               │
│  • Profit Factor: 2.0x • BULL_PUT NIFTY -₹500                 │
│  • Sharpe Ratio: 1.85  • BULL_PUT NIFTY +₹1,800               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Strategies
```
┌─────────────────────────────────────────────────────────────────┐
│ Strategy Generator                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Underlying: [NIFTY] [BANKNIFTY] [FINNIFTY]                    │
│  Capital: ₹100,000     Lots: 1                                 │
│  Risk Mode: [Conservative] [Balanced] [Aggressive]             │
│                                                                   │
│  ┌──────────────────────────────────────────────┐              │
│  │    Run Strategy Analysis                     │              │
│  └──────────────────────────────────────────────┘              │
│                                                                   │
│  ✅ APPROVED                                                    │
│  Strategy: BULL_PUT                                             │
│  Signal: BULLISH (85% confidence)                              │
│  IV Regime: NORMAL                                              │
│                                                                   │
│  Trade Ticket:                                                  │
│  • Lot Size: 65      • Lots: 1                                 │
│  • Legs:                                                        │
│    ├─ SELL CE 20100                                            │
│    └─ BUY CE 20200                                             │
│                                                                   │
│  ┌──────────────────────────────────────────────┐              │
│  │    Execute Trade                             │              │
│  └──────────────────────────────────────────────┘              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Positions
```
┌─────────────────────────────────────────────────────────────────┐
│ Open Positions                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Open: 3      Total P&L: ₹4,200 (2.1%)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────┐               │
│  │ ⬆️  BULL_PUT NIFTY                +₹2,100   │               │
│  │ Opened: Jan 5, 10:30 AM                     │               │
│  ├─────────────────────────────────────────────┤               │
│  │ Entry: ₹340  Current: ₹380  TP: 2000  SL: -2000            │
│  │                                    Return: +1.8%            │
│  │ ┌───────────────────────────────────────┐  │               │
│  │ │         Close Position                │  │               │
│  │ └───────────────────────────────────────┘  │               │
│  └─────────────────────────────────────────────┘               │
│                                                                   │
│  Risk Metrics:  Portfolio Heat: 2.5% | Max DD: -1.2%          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📱 MOBILE APP LAYOUT

### Dashboard (Mobile)
```
┌─────────────────────┐
│ FastTrade Pro  🟢   │
├─────────────────────┤
│                     │
│ ┌─────────────────┐ │
│ │ Capital         │ │
│ │ ₹100,000        │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Today's P&L     │ │
│ │ ₹3,200 (+3.2%)  │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Trades          │ │
│ │ 5               │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Win Rate        │ │
│ │ 80%             │ │
│ └─────────────────┘ │
│                     │
│ Portfolio Chart     │
│ ═══════════════════ │
│ ╱╲ ╱╲              │
│╱  ╲╱  ╲╱╲          │
│                     │
│ Recent Trades:      │
│ • BULL_PUT +₹2100  │
│ • BEAR_CALL +₹1500 │
│ • BULL_PUT -₹500   │
│                     │
├─────────────────────┤
│📊 📊 💼 📖 ⚙️      │  ← Tab Navigation
└─────────────────────┘
```

### Strategies (Mobile)
```
┌─────────────────────┐
│ Strategy Generator  │
├─────────────────────┤
│                     │
│ Underlying          │
│ ┌─────────────────┐ │
│ │ NIFTY ▼         │ │
│ └─────────────────┘ │
│                     │
│ Capital (₹)         │
│ ┌─────────────────┐ │
│ │ 100000          │ │
│ └─────────────────┘ │
│                     │
│ Lots                │
│ ┌─────────────────┐ │
│ │ 1               │ │
│ └─────────────────┘ │
│                     │
│ Risk Mode           │
│ ┌─────────────────┐ │
│ │ BALANCED ▼      │ │
│ └─────────────────┘ │
│                     │
│ ┌─────────────────┐ │
│ │ Run Strategy    │ │
│ └─────────────────┘ │
│                     │
│ ✅ APPROVED        │
│ BULL_PUT          │
│ "Strong bullish"  │
│                     │
│ ┌─────────────────┐ │
│ │ Execute Trade   │ │
│ └─────────────────┘ │
│                     │
├─────────────────────┤
│📊 ⚡ 💼 📖 ⚙️      │
└─────────────────────┘
```

---

## 🎨 COLOR & TYPOGRAPHY REFERENCE

### Color Palette
```
Primary (Green)      #10B981  ████████████
Secondary (Blue)     #3B82F6  ████████████
Danger (Red)         #EF4444  ████████████
Warning (Orange)     #F59E0B  ████████████
Background (Dark)    #0f172a  ████████████
Card (Dark)          #1e293b  ████████████
Text (Light)         #f1f5f9  ████████████
Text (Muted)         #94a3b8  ████████████
```

### Typography
```
Desktop:
H1 (28px, Bold)     - Page titles
H2 (24px, Bold)     - Section headers
H3 (20px, Semibold) - Card titles
Body (16px)         - Regular text
Small (14px)        - Secondary text
Tiny (12px)         - Labels

Mobile:
H1 (24px, Bold)     - Page titles
H2 (18px, Semibold) - Section headers
Body (14px)         - Regular text
Small (12px)        - Secondary text
```

---

## 📐 COMPONENT LIBRARY

### Buttons
```
Primary Button
┌─────────────────────┐
│  Run Strategy       │  Green (#10B981)
└─────────────────────┘

Secondary Button
┌─────────────────────┐
│  Execute Trade      │  Blue (#3B82F6)
└─────────────────────┘

Danger Button
┌─────────────────────┐
│  Close Position     │  Red (#EF4444)
└─────────────────────┘
```

### Cards (Glass-morphism)
```
┌──────────────────────────┐
│  Card Title              │
├──────────────────────────┤
│                          │
│  Content here            │
│  Semi-transparent bg     │
│  Subtle border           │
│                          │
└──────────────────────────┘
```

### Input Fields
```
Label
┌──────────────────────────┐
│ Input value              │
└──────────────────────────┘

Select Dropdown
┌──────────────────────────┐
│ Selected Option      ▼   │
└──────────────────────────┘

Toggle Switch
ON   ⚪
OFF  ⚫
```

---

## 🎯 INTERACTION PATTERNS

### Trade Execution Flow
```
1. Configure Strategy
   ↓
2. Run Analysis
   ↓
3. Review Result
   ↓
4. Approve/Reject
   ↓
5. Execute Trade
   ↓
6. Monitor Position
   ↓
7. Close or TP/SL
```

### Data Updates
```
Real-time MtM updates every 1 minute
Strategy signals checked every 15 minutes
Daily stats reset at market close
Position tracking 24/7
```

---

## 📊 RESPONSIVE BREAKPOINTS

### Web
- **Desktop**: 1024px+ (Full sidebar + content)
- **Tablet**: 768px-1023px (Compact sidebar)
- **Mobile**: <768px (Bottom nav)

### Mobile
- **iOS**: 375px-430px (iPhone)
- **Android**: 360px-720px (Various devices)
- **Tablets**: 600px+ (iPad)

---

## 🌟 VISUAL HIERARCHY

### Web
```
Header (Navigation + System Status)
────────────────────────────────────
│                                 │
│  Sidebar    │    Main Content   │
│             │                   │
│  - Home     │  Metric Cards     │
│  - Strat    │  Charts           │
│  - Pos      │  Tables           │
│  - Journal  │  Forms            │
│  - Settings │                   │
│             │                   │
└─────────────────────────────────┘
```

### Mobile
```
┌─────────────────────┐
│      Content        │
│    (Scrollable)     │
└─────────────────────┘
┌─────────────────────┐
│  Tab Navigation     │  ← Always visible
│  📊 ⚡ 💼 📖 ⚙️    │
└─────────────────────┘
```

---

## ✨ SPECIAL FEATURES

### Animations
- Smooth page transitions
- Button hover effects
- Chart animations
- Fade-in on load
- Scroll-triggered reveals

### Accessibility
- ARIA labels
- Keyboard navigation
- High contrast mode
- Mobile-friendly touch targets
- Clear error messages

### Performance
- Lazy-loaded routes
- Optimized images
- Code splitting
- Efficient re-renders
- Caching strategies

---

## 🎬 USER FLOW EXAMPLES

### First Time User
```
1. Land on Dashboard
   ↓
2. Configure capital & risk in Settings
   ↓
3. View Strategies page
   ↓
4. Run strategy analysis
   ↓
5. Approve and execute trade
   ↓
6. Monitor in Positions
   ↓
7. Review in Journal
```

### Experienced Trader
```
1. Quick dashboard check
   ↓
2. Open Strategies (muscle memory)
   ↓
3. Review signal (trust system)
   ↓
4. One-click execute
   ↓
5. Monitor via mobile
   ↓
6. Auto-exit on TP/SL
```

---

## 📱 COMPARISON: WEB vs MOBILE

| Feature | Web | Mobile |
|---------|-----|--------|
| Dashboard | Full charts | Compact metrics |
| Strategies | Detailed form | Quick input |
| Positions | Large table | Card list |
| Journal | Full analytics | Coming soon |
| Settings | All options | Coming soon |
| Offline | No | Coming soon |
| Notifications | In-app | Coming soon |
| Performance | Optimized | Fast |

---

**All UI elements are production-ready and can be deployed immediately.**

Created: January 5, 2026  
Last Updated: January 5, 2026
