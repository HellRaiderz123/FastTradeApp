import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.core.ml.dataset import _load_candles_df
from app.core.ml.feature_builder import build_features_from_df
from app.core.ml.labeling import add_future_return_labels
from app.core.ml.config import StockMLConfig

db = SessionLocal()
config = StockMLConfig()
raw = _load_candles_df(db, 'RELIANCE', 'daily', 500)
print('raw rows:', len(raw))
print('raw index type:', type(raw.index[0]))

features = build_features_from_df(raw, config)
print('features rows:', len(features))
print('features index:', features.index[:3].tolist(), '...', features.index[-3:].tolist())

labeled = add_future_return_labels(features, config)
print('labeled rows:', len(labeled))
print('labeled index:', labeled.index[:3].tolist(), '...', labeled.index[-3:].tolist())

# Recompute future return on labeled to check alignment
labeled2 = labeled.copy()
labeled2['rc'] = labeled2['close'].shift(-config.horizon)
labeled2['rr'] = (labeled2['rc'] / labeled2['close']) - 1
labeled2 = labeled2.dropna(subset=['rr'])

up = labeled2[labeled2['label'] == 1]['rr'].mean()
dn = labeled2[labeled2['label'] == 0]['rr'].mean()
print(f'Label=1 mean future_ret: {up:.4f}')
print(f'Label=0 mean future_ret: {dn:.4f}')
print(f'Alignment OK: {up > 0 and dn < 0}')

# Also check: what does the raw labeling produce before dropna
raw_labeled = features.copy()
raw_labeled['future_close'] = raw_labeled['close'].shift(-config.horizon)
raw_labeled['future_ret'] = (raw_labeled['future_close'] / raw_labeled['close']) - 1
raw_labeled['label_check'] = (raw_labeled['future_ret'] >= config.return_threshold).astype(int)
print()
print('Direct label check on features (no dropna):')
print('  UP rows:', (raw_labeled['label_check'] == 1).sum())
print('  DOWN rows:', (raw_labeled['label_check'] == 0).sum())
print('  NaN future_ret:', raw_labeled['future_ret'].isna().sum())

db.close()
