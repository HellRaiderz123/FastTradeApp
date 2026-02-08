-- Sample Stock Strategies for NIFTY 50 Stocks
-- Run this SQL to create some example strategies

-- 1. RELIANCE Momentum Strategy
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'RELIANCE Momentum 15m',
  'Momentum-based strategy for RELIANCE using RSI and moving averages',
  'stock_momentum_15m',
  'RELIANCE',
  '{"min_confidence": 65, "rsi_threshold": 50, "risk_percent": 2.0, "reward_multiple": 1.5}',
  true,
  'system'
);

-- 2. TCS Trend Following Strategy
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'TCS Trend Following 15m',
  'Trend following strategy for TCS using ADX and directional indicators',
  'stock_trend_following_15m',
  'TCS',
  '{"min_confidence": 70, "adx_threshold": 25, "risk_percent": 2.5, "reward_multiple": 2.0}',
  true,
  'system'
);

-- 3. INFY Mean Reversion Strategy
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'INFY Mean Reversion 15m',
  'Mean reversion strategy for INFY using Bollinger Bands',
  'stock_mean_reversion_15m',
  'INFY',
  '{"min_confidence": 60, "bb_period": 20, "bb_std": 2.0, "risk_percent": 1.5, "reward_multiple": 2.0}',
  true,
  'system'
);

-- 4. HDFCBANK Universal Momentum (works for all stocks)
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'Universal Stock Momentum',
  'Generic momentum strategy that works for any NIFTY 50 stock',
  'stock_momentum_15m',
  '',  -- Empty underlying means it works for all symbols
  '{"min_confidence": 70, "rsi_threshold": 55, "risk_percent": 2.0, "reward_multiple": 1.5}',
  true,
  'system'
);

-- 5. ICICIBANK Aggressive Momentum
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'ICICIBANK Aggressive Momentum',
  'Higher risk momentum strategy for ICICIBANK',
  'stock_momentum_15m',
  'ICICIBANK',
  '{"min_confidence": 60, "rsi_threshold": 50, "risk_percent": 3.0, "reward_multiple": 2.0}',
  true,
  'system'
);

-- 6. SBIN Conservative Trend
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'SBIN Conservative Trend',
  'Conservative trend following for SBIN with tight risk management',
  'stock_trend_following_15m',
  'SBIN',
  '{"min_confidence": 75, "adx_threshold": 30, "risk_percent": 1.5, "reward_multiple": 2.5}',
  true,
  'system'
);

-- 7. WIPRO Mean Reversion
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'WIPRO Mean Reversion',
  'Mean reversion strategy for WIPRO using standard Bollinger Band settings',
  'stock_mean_reversion_15m',
  'WIPRO',
  '{"min_confidence": 65, "bb_period": 20, "bb_std": 2.0, "risk_percent": 2.0, "reward_multiple": 1.8}',
  true,
  'system'
);

-- 8. HCLTECH High Frequency Momentum
INSERT INTO strategy_configs (name, description, strategy_type, underlying, parameters, enabled, created_by)
VALUES (
  'HCLTECH Quick Momentum',
  'Fast-moving momentum strategy for HCLTECH with lower confidence requirements',
  'stock_momentum_15m',
  'HCLTECH',
  '{"min_confidence": 55, "rsi_threshold": 48, "risk_percent": 1.8, "reward_multiple": 1.5}',
  true,
  'system'
);

-- View all created strategies
SELECT id, name, strategy_type, underlying, enabled, created_at 
FROM strategy_configs 
WHERE strategy_type LIKE 'stock_%' 
ORDER BY created_at DESC;
