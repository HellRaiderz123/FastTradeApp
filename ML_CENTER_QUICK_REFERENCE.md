# FastTrade ML Center - Quick Reference Card

## 🧠 Where to Find ML

**Icon**: Brain icon in left sidebar  
**URL**: `localhost:3000/ml`  
**Menu Position**: Between Calendar & Strategies  

---

## 📊 Dashboard Cards at a Glance

| Card | Color | Shows | Target |
|------|-------|-------|--------|
| **Model Status** | Blue/Yellow/Red | Training state | "Ready" |
| **Accuracy** | Blue | % correct | > 60% |
| **Training Samples** | Purple | Data points | > 500 |
| **Precision** | Green | Positive accuracy | > 65% |
| **Recall** | Yellow | Signal discovery | > 55% |
| **F1 Score** | Red | Overall quality | > 60% |

---

## 🎮 Controls Explained

```
┌─────────────────────────────────────┐
│  ML SETTINGS                        │
├─────────────────────────────────────┤
│ Enable ML Suggestions    [◉ Toggle] │ ← Turn ON/OFF
│ Confidence: 70%         [═════●════]│ ← Move slider
│ Auto Train              [◉ Toggle]  │ ← Schedule retraining
│ Retraining Schedule     [Weekly ▼]  │ ← Select frequency
│ [Save ML Settings Button]           │ ← Click to save
└─────────────────────────────────────┘
```

---

## ⚡ Common Actions

### Start Trading with ML
```
1. Go to ML Center
2. Click "Train Now" (wait 10s)
3. Verify Accuracy > 55%
4. Set Confidence to 70%
5. Toggle Enable ML = ON
6. Click Save Settings
7. Go to Trading Terminal
8. See ML signals in suggestions
9. Trade! 🚀
```

### Train Model
```
ML Center → [Train Now Button] → Wait → See Metrics
```

### Change Confidence
```
ML Center → Slide confidence bar → Save
```

### Enable Auto-Training
```
ML Center → Toggle Auto Train ON → Select Weekly → Save
```

---

## 🎯 Confidence Threshold Guide

| Level | Type | Best For |
|-------|------|----------|
| **50-60%** | Very Aggressive | Testing, experimental |
| **65-75%** | Moderate | Default, balanced |
| **80-95%** | Conservative | Capital preservation |

---

## 📈 How to Read Metrics

### Ideal Ranges
- **Accuracy**: 55-70% (better = more correct)
- **Precision**: 60-75% (better = fewer false alarms)
- **Recall**: 50-70% (better = catches more signals)
- **F1 Score**: 55-70% (balance of precision/recall)

### Troubleshooting
- **All metrics low?** → Train model, increase dataset
- **Accuracy > 70% but Precision low?** → Raise confidence slider
- **Metrics old?** → Model needs retraining (click Train Now)

---

## 🔗 Integration Points

### With Trading Terminal
```
Terminal → Search Stock → Trade Suggestions Panel
Shows: TA Signals + ML Signals
Confidence score visible next to each ML suggestion
If ML confidence > threshold → Signal appears ✓
```

### Settings Still in Old Place?
Yes, but now with ML Center you don't need to go there!
- Old location: Settings page (too buried)
- New location: ML Center (easy to find) ✓

---

## 🚨 Troubleshooting Quick Help

| Problem | Solution |
|---------|----------|
| Model shows "Not Trained" | Click [Train Now] button |
| Accuracy = 0% | Wait for training to complete |
| Settings not saving | Check network, reload page |
| ML signals not showing | Enable toggle, check confidence |
| Page blank | Refresh browser, check console |

---

## 📱 Mobile View Tips

- Metrics stack vertically
- Slider easier to adjust on mobile
- Saves horizontal space
- Settings still responsive
- Touch-friendly buttons

---

## 🔐 Data Safety

✅ Settings saved to:
- Local browser storage (instant)
- Backend database (persistent)
- Both locations stay in sync

✅ No data loss:
- Even if browser cleared, backend copy saved
- Reloading page retrieves all settings
- Auto-sync on every save

---

## 📞 Common Q&A

**Q: Should ML be ON always?**  
A: Yes, if accuracy > 55% and settings configured

**Q: When to retrain?**  
A: Weekly auto-train sufficient, or manually before big trades

**Q: What if accuracy drops?**  
A: Market regime changed. Retrain or raise confidence threshold

**Q: Override low confidence?**  
A: Not recommended. Raise threshold instead

**Q: Can I use old threshold?**  
A: No, saves immediately. Use browser refresh to cancel

---

## 🎓 Understanding the ML Model

### 13 Features Analyzed
RSI, MACD (3x), ADX, EMA (2x), Bollinger Bands, ATR, Returns, Volatility, Volume

### Algorithm
Binary classifier using LogisticRegression (Bullish/Bearish)

### Training Data
All historical 15m & daily candles from local database

### Retraining
Automated weekly (Sundays 4 AM IST) or manual on-demand

### Confidence Score
0.50 = random guess | 0.65 = decent | 0.95 = very confident

---

## 💡 Pro Tips

1. **Start Conservative** (confidence 75-80%) → Adjust down if missing trades
2. **Check Weekly** → Ensure accuracy stays > 55%
3. **Combine Signals** → Use ML + TA together (better results)
4. **Paper Trade First** → Test ML for 2 weeks before live
5. **Keep Logs** → Track which signals worked for analysis
6. **Retrain Often** → Keep model fresh with latest patterns

---

## 🚀 Next Step

### Right Now
1. Go to ML Center (click sidebar)
2. Check model status
3. If not "Ready" → Click [Train Now]
4. Wait for metrics to populate
5. Verify Accuracy > 50%
6. Enable toggle
7. Start trading!

### This Week
- [ ] Train model
- [ ] Configure threshold (70%)
- [ ] Enable auto-train
- [ ] Test in paper trading
- [ ] Monitor accuracy

### This Month
- [ ] Optimize threshold for your strategy
- [ ] Track win rate with ML signals
- [ ] Compare to TA alone
- [ ] Adjust based on results

---

## 📋 Pre-Trading Checklist

- [ ] ML Center page loads without errors
- [ ] Model status = "Ready"
- [ ] Accuracy > 55%
- [ ] ML toggle = ON
- [ ] Confidence threshold = set (default 70%)
- [ ] Settings saved ✓
- [ ] Trading Terminal shows ML suggestions
- [ ] Ready to trade!

---

**Print this card and keep it handy!**  
**Last Updated**: December 2024  
**Version**: 1.0
