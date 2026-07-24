import sys; sys.path.insert(0, '/app')
from app.core.ml import ensemble
import inspect

src_train   = inspect.getsource(ensemble.train_ensemble)
src_split   = inspect.getsource(ensemble._per_symbol_split)
src_predict = inspect.getsource(ensemble.predict_ensemble)

print("Ensemble fixes check:")
print("  per_symbol_split (val_idx)  :", 'val_idx' in src_split)
print("  _balance_train called       :", '_balance_train' in src_train)
print("  calibrated threshold        :", 'best_threshold' in src_train)
print("  no sample_weight hack       :", 'sample_weight' not in src_train)
print("  decision_threshold in meta  :", 'decision_threshold' in src_train)
print("  predict uses threshold      :", 'decision_threshold' in src_predict)
print("  predict uses +/-0.05 band   :", '0.05' in src_predict)
print()
print("All OK:", all([
    'val_idx' in src_split,
    '_balance_train' in src_train,
    'best_threshold' in src_train,
    'sample_weight' not in src_train,
    'decision_threshold' in src_train,
    'decision_threshold' in src_predict,
]))
