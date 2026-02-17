# ML Center - Quick Start Guide

## Overview
The **ML Center** is your one-stop dashboard for managing, monitoring, and training the FastTrade machine learning model. It's now visible in the main sidebar navigation for easy access.

---

## 📍 Accessing ML Center

1. **From Sidebar**: Click the **ML Center** icon (brain icon) in the left navigation
2. **Direct URL**: Navigate to `/ml` in the browser
3. **Quick Access**: Use the search/command palette to jump to ML features

---

## 🎯 Key Features

### 1. **Model Status Dashboard**
Shows current state of your ML model:
- **Status**: Ready | Training | Not Trained | Error
- **Last Training Date**: When the model was last trained
- **Color coding**: Green (ready), Yellow (training), Red (error)

### 2. **Performance Metrics**
Real-time accuracy and quality indicators:

| Metric | What It Means | Target |
|--------|---------------|--------|
| **Accuracy** | % correct predictions | > 55% |
| **Precision** | % positive predictions correct | > 60% |
| **Recall** | % actual positives found | > 50% |
| **F1 Score** | Harmonic mean of precision/recall | > 55% |
| **Training Samples** | Data points used for training | > 500 |

### 3. **Train Now Button**
- Manually trigger ML model training
- Training logs display in real-time
- Shows accuracy, precision, F1 score after completion
- Takes 5-15 seconds depending on data size

### 4. **ML Settings**

#### Enable/Disable ML
Toggle ML suggestions on/off without losing configuration

#### Confidence Threshold
- Slider: 50% to 95%
- **What it does**: Only show suggestions above this confidence level
- **Lower (50-60%)**: More signals, but less reliable
- **Higher (75-95%)**: Fewer signals, higher accuracy
- **Recommended**: 65-75% for balanced approach

#### Auto Train Enable
- Auto-retrains model on schedule
- Keeps model fresh with latest market data
- Set schedule: Daily, Weekly, Bi-weekly, Monthly

#### Retraining Schedule
- **Daily**: Updates every trading day (4 AM IST)
- **Weekly**: Updates every Sunday (4 AM IST) 
- **Bi-Weekly**: Updates every 2 weeks
- **Monthly**: Updates once per month

### 5. **Save Settings**
All changes saved to both:
- Browser localStorage (instant)
- Backend database (persistent)

---

## 🚀 Getting Started

### Step 1: Check Model Status
1. Navigate to ML Center
2. Check if model status shows "ready"
3. If not trained, click "Train Now"

### Step 2: Configure Settings
1. Toggle "Enable ML Suggestions" ON
2. Set confidence threshold to **70%** (balanced)
3. Enable "Auto Train" for weekly retraining
4. Click "Save ML Settings"

### Step 3: Test ML Signals
1. Go to **Trading Terminal** (`/`)
2. Search for a stock (e.g., RELIANCE)
3. ML suggestions will appear if confidence > threshold
4. Compare ML + TA signals in "Trade Suggestions" panel

### Step 4: Monitor Performance
1. Return to ML Center weekly
2. Check accuracy metrics
3. Adjust confidence threshold if needed
4. Manually train before major market events

---

## 🔧 Common Tasks

### Train Model Immediately
```
1. Click "Train Now" button
2. Wait for training logs to show ✓
3. Metrics update automatically
```

### Change Confidence Level
```
1. Move "Confidence Threshold" slider
2. Lower = more signals (risky)
3. Higher = fewer signals (safer)
4. Click "Save ML Settings"
```

### Enable Automatic Training
```
1. Toggle "Auto Train Model" ON
2. Select retraining schedule
3. Schedule: Sundays 4 AM IST (weekly)
4. Click "Save ML Settings"
```

### Check Model Accuracy
```
1. Look at Accuracy card (blue)
2. Precision card (green)
3. Recall card (yellow)
4. F1 Score card (red)
5. If < 55%, consider training with more data
```

---

## 📊 Understanding Metrics

### **Accuracy** (Blue Card)
- Percentage of all predictions that were correct
- Formula: (True Positives + True Negatives) / Total
- **Good**: > 55% | **Excellent**: > 65%

### **Precision** (Green Card)
- When model says "BUY", how often is it right?
- Formula: True Positives / (True Positives + False Positives)
- **Good**: > 60% | **Excellent**: > 70%

### **Recall** (Yellow Card)
- What % of actual buy signals did the model find?
- Formula: True Positives / (True Positives + False Negatives)
- **Good**: > 50% | **Excellent**: > 60%

### **F1 Score** (Red Card)
- Balanced metric combining precision & recall
- **Good**: > 55% | **Excellent**: > 65%

---

## ⚙️ Fine-tuning for Your Strategy

### Conservative Traders
```
Confidence Threshold: 80-85%
Auto Train: Enabled (weekly)
Result: Only high-confidence signals
```

### Moderate Traders
```
Confidence Threshold: 70-75%
Auto Train: Enabled (weekly)
Result: Balanced signals and reliability
```

### Aggressive Traders
```
Confidence Threshold: 55-65%
Auto Train: Enabled (daily)
Result: More signals, requires active management
```

---

## 🐛 Troubleshooting

### "Model Status shows 'Not Trained'"
**Solution**: Click "Train Now" button and wait 5-15 seconds

### "Training takes too long"
**Cause**: Large amount of historical data
**Solution**: Check backend logs, or wait for automatic daily cleanup

### "ML suggestions not appearing in Terminal"
**Checklist**:
- [ ] ML toggle enabled in ML Center
- [ ] ML suggestions enabled in Settings
- [ ] Confidence threshold not too high
- [ ] Browser localStorage enabled
- [ ] Refresh page and try again

### "Accuracy is very low (< 50%)"
**Possible causes**:
1. Insufficient training data (< 500 samples)
2. Market regime change not captured
3. Poor feature engineering
4. Overfitting to historical data

**Solution**: Train with more recent data, adjust confidence threshold higher

### "Settings not saving"
**Checklist**:
- [ ] Network connection active
- [ ] Backend API running (`http://localhost:8000` accessible)
- [ ] Browser console shows no errors
- [ ] Try saving again

---

## 📈 ML Model Details

### Features Used (13 Total)
The ML model analyzes these 13 technical indicators:

1. **RSI (14)** - Momentum reversal indicator
2. **MACD** - Trend momentum (3 features: momentum, signal, histogram)
3. **ADX (14)** - Trend strength
4. **EMA (12 & 26)** - Trend direction
5. **Bollinger Bands** - Volatility positioning
6. **ATR (14)** - Volatility measurement
7. **Returns (5D)** - Price momentum
8. **Volatility (10D)** - Price volatility
9. **Volume SMA (5)** - Volume trend

### Model Type
- **Algorithm**: Logistic Regression
- **Design**: Binary classification (Bullish / Bearish)
- **Training**: Weekly on Sundays 4 AM IST
- **Features**: Normalized via StandardScaler
- **Test Split**: 80/20 temporal split

### How to Interpret Confidence
- **Confidence = 0.85** = Model is 85% sure this is a bullish signal
- **Confidence = 0.52** = Model barely confident, almost a coin flip
- **Below threshold** = Signal rejected, not shown to trader

---

## 🎓 ML Best Practices

### 1. Train Regularly
- Auto-train enabled ✅
- Manual train before major events (earnings, Fed meetings)
- Retrain if accuracy drops below 55%

### 2. Monitor Accuracy
- Check metrics weekly
- Track accuracy over time
- Alert if accuracy drops suddenly (market regime change)

### 3. Adjust Confidence Threshold
- Start at 70%
- Lower if missing good trades
- Raise if too many false signals
- Keep logs of changes for analysis

### 4. Combine with Technical Analysis
- ML is one tool, not the only tool
- Always check support/resistance levels
- Verify volume, trend, momentum
- Use for signal confirmation, not blind execution

### 5. Backtest Before Live Trading
- Test ML signals in Backtest engine first
- Verify profitability over 3+ months
- Ensure positive expectancy
- Then trade in paper mode for 2+ weeks

---

## 🔗 Integration with Other Features

### Trading Terminal
- ML signals appear in "Trade Suggestions" panel
- Confidence score shown alongside TA signals
- Combined signal = TA + ML agreement

### Stock Strategies
- Can toggle ML override for any stock
- ML wins when confidence high AND threshold met
- Falls back to TA if ML not trained

### Backtest Engine
- Test strategies WITH or WITHOUT ML
- Compare returns: TA-only vs TA+ML hybrid
- Optimize parameters before live trading

### Journal
- Track which trades used ML
- Mark as "ML Win" or "ML Loss"
- Identify patterns in ML success/failure

---

## 📞 Support

### Common Questions

**Q: How often should I train?**
A: Weekly (auto) + manually before major events = ideal

**Q: Will ML make me rich?**
A: ML is a tool, not magic. Use with proper risk management.

**Q: What if accuracy is 51%?**
A: Just slightly better than coin flip. Increase confidence threshold to 85%+

**Q: Can I use same model for all stocks?**
A: Yes, current model trained on all stocks. Can optimize per-stock in Phase 5.

**Q: How do I know when to disable ML?**
A: If accuracy < 50% or market is extremely volatile/choppy.

---

## 🎯 Next Steps After Setup

1. **Week 1**: Train model, set threshold 70%, monitor in paper trading
2. **Week 2**: Check accuracy metrics, test in Trading Terminal
3. **Week 3**: Start live trading with minimal position size
4. **Week 4**: Review performance, optimize threshold
5. **Ongoing**: Weekly retraining, monthly accuracy review

---

**Version**: 1.0  
**Last Updated**: December 2024  
**Status**: ✅ Active and Production-Ready
