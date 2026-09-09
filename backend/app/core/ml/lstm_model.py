"""LSTM-based stock prediction model for time-series forecasting."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import _load_candles_df, build_stock_ml_dataset
from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS
from app.core.ml.overfitting import check_overfitting

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model as keras_load
    from tensorflow.keras.layers import LSTM, Dense, Dropout, LayerNormalization, Input
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.optimizers import Adam
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not installed. LSTM model unavailable.")


def _create_sequences(X: np.ndarray, y: np.ndarray, seq_length: int) -> Tuple[np.ndarray, np.ndarray]:
    """Extract rolling sequences of length seq_length."""
    if len(X) <= seq_length:
        return np.empty((0, seq_length, X.shape[1])), np.empty((0,))
    
    # Vectorized sliding window
    X_seq = np.lib.stride_tricks.sliding_window_view(X[:-1], window_shape=(seq_length, X.shape[1])).squeeze(1)
    y_seq = y[seq_length:]
    return X_seq, y_seq


def _per_symbol_split_lstm(
    x: pd.DataFrame, 
    y: pd.Series,
    feature_cols: List[str],
    seq_length: int,
    test_ratio: float = 0.2, 
    val_ratio: float = 0.15
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, RobustScaler]:
    """Chronologically split per-symbol sequences without boundary data loss."""
    train_X, train_y = [], []
    val_X, val_y = [], []
    test_X, test_y = [], []
    
    # RobustScaler handles financial outliers better than StandardScaler
    scaler = RobustScaler()
    
    # Pass 1: Fit scaler ONLY on training splits across all symbols
    train_raw_list = []
    symbol_groups = []
    
    for symbol, grp in x.groupby("symbol", sort=False):
        grp = grp.sort_index()
        n = len(grp)
        min_required = seq_length * 3 + 20
        if n < min_required:
            continue
            
        t_cut = int(n * (1.0 - test_ratio - val_ratio))
        v_cut = int(n * (1.0 - test_ratio))
        
        train_raw_list.append(grp[feature_cols].iloc[:t_cut].values)
        grp_y = y.loc[grp.index]
        symbol_groups.append((grp, grp_y, t_cut, v_cut))
        
    if not train_raw_list:
        return (np.array([]),) * 6 + (scaler,)
        
    scaler.fit(np.vstack(train_raw_list))
    
    # Pass 2: Scale and create sequences with warm-up lookback padding
    for grp, grp_y, t_cut, v_cut in symbol_groups:
        X_all = scaler.transform(grp[feature_cols].values)
        y_all = grp_y.values
        
        # Train slice
        X_tr, y_tr = _create_sequences(X_all[:t_cut], y_all[:t_cut], seq_length)
        
        # Val slice (prefixed with seq_length rows from train to eliminate data loss)
        val_start = max(0, t_cut - seq_length)
        X_va, y_va = _create_sequences(X_all[val_start:v_cut], y_all[val_start:v_cut], seq_length)
        
        # Test slice (prefixed with seq_length rows from val)
        test_start = max(0, v_cut - seq_length)
        X_te, y_te = _create_sequences(X_all[test_start:], y_all[test_start:], seq_length)
        
        if len(X_tr) > 0:
            train_X.append(X_tr); train_y.append(y_tr)
        if len(X_va) > 0:
            val_X.append(X_va); val_y.append(y_va)
        if len(X_te) > 0:
            test_X.append(X_te); test_y.append(y_te)

    return (
        np.concatenate(train_X) if train_X else np.empty((0, seq_length, len(feature_cols))),
        np.concatenate(train_y) if train_y else np.empty((0,)),
        np.concatenate(val_X) if val_X else np.empty((0, seq_length, len(feature_cols))),
        np.concatenate(val_y) if val_y else np.empty((0,)),
        np.concatenate(test_X) if test_X else np.empty((0, seq_length, len(feature_cols))),
        np.concatenate(test_y) if test_y else np.empty((0,)),
        scaler
    )


def _build_lstm_model(seq_length: int, n_features: int) -> "Sequential":
    """Regularised LSTM architecture to reduce overfitting."""
    from tensorflow.keras.regularizers import l2
    model = Sequential([
        Input(shape=(seq_length, n_features)),
        LSTM(32, return_sequences=True, dropout=0.3, recurrent_dropout=0.2,
             kernel_regularizer=l2(1e-4)),
        LayerNormalization(),

        LSTM(16, return_sequences=False, dropout=0.3, recurrent_dropout=0.2,
             kernel_regularizer=l2(1e-4)),
        LayerNormalization(),

        Dense(8, activation='relu', kernel_regularizer=l2(1e-4)),
        Dropout(0.3),
        Dense(1, activation='sigmoid')
    ])

    model.compile(
        optimizer=Adam(learning_rate=0.001, clipnorm=1.0),
        loss='binary_crossentropy',
        metrics=['accuracy', tf.keras.metrics.AUC(name='roc_auc')]
    )
    return model


def _optimize_threshold_on_val(y_val: np.ndarray, y_proba_val: np.ndarray) -> float:
    """Find threshold maximising F1 on val set.
    Pred rate must be 15-55%. Prefers higher precision on ties.
    Falls back to 0.45 if no valid threshold found.
    """
    best_t, best_f1, best_p = 0.45, 0.0, 0.0
    for t in np.arange(0.30, 0.75, 0.01):
        preds = (y_proba_val >= t).astype(int)
        rate = preds.mean()
        if rate < 0.15 or rate > 0.55:
            continue
        p = precision_score(y_val, preds, zero_division=0)
        r = recall_score(y_val, preds, zero_division=0)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1 or (f1 == best_f1 and p > best_p):
            best_f1, best_p, best_t = f1, p, t
    return round(float(best_t), 3)


def train_lstm_model(
    db: Session, 
    symbols: List[str], 
    config: StockMLConfig,
    seq_length: int = 15,
    epochs: int = 40,
    batch_size: int = 256
) -> Dict:
    """Train and evaluate the LSTM model."""
    if not TF_AVAILABLE:
        raise ImportError("TensorFlow is required.")
        
    x, y = build_stock_ml_dataset(db, symbols, config)
    if x.empty or len(x) < config.min_rows:
        raise ValueError(f"Insufficient data: {len(x)} rows")
        
    X_train, y_train, X_val, y_val, X_test, y_test, scaler = _per_symbol_split_lstm(
        x, y, FEATURE_COLUMNS, seq_length, test_ratio=0.15, val_ratio=0.15
    )
    
    if len(X_train) == 0 or len(X_val) == 0:
        raise ValueError("Failed to generate train/validation sequences.")

    logger.info(f"Sequences -> Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # Balanced class weighting
    n_pos = np.sum(y_train == 1)
    n_neg = np.sum(y_train == 0)
    total = len(y_train)
    class_weight = {0: total / (2.0 * max(n_neg, 1)), 1: total / (2.0 * max(n_pos, 1))}

    model = _build_lstm_model(seq_length, len(FEATURE_COLUMNS))
    
    callbacks = [
        EarlyStopping(monitor='val_loss', mode='min', patience=12, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6)
    ]
    
    # Shuffle train sequences to break per-symbol block ordering
    idx = np.random.permutation(len(X_train))
    X_train, y_train = X_train[idx], y_train[idx]

    # No class weighting — let precision floor in threshold search handle imbalance
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=max(batch_size, 256),
        callbacks=callbacks,
        verbose=1
    )
    
    # 1. Optimize threshold on VALIDATION set
    y_val_proba = model.predict(X_val, verbose=0).flatten()
    best_threshold = _optimize_threshold_on_val(y_val, y_val_proba)
    
    # 2. Evaluate performance on OUT-OF-SAMPLE TEST set
    y_test_proba = model.predict(X_test, verbose=0).flatten()
    y_test_pred = (y_test_proba >= best_threshold).astype(int)
    
    accuracy = float(accuracy_score(y_test, y_test_pred))
    precision = float(precision_score(y_test, y_test_pred, zero_division=0))
    recall = float(recall_score(y_test, y_test_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_test_pred, zero_division=0))
    roc_auc = float(roc_auc_score(y_test, y_test_proba)) if len(np.unique(y_test)) > 1 else 0.5
    
    # Train accuracy for overfitting check
    y_train_proba = model.predict(X_train, verbose=0).flatten()
    y_train_pred = (y_train_proba >= best_threshold).astype(int)
    train_accuracy = float(accuracy_score(y_train, y_train_pred))

    # Overfitting diagnostics (includes LSTM loss divergence check)
    overfit_report = check_overfitting(
        train_accuracy=train_accuracy,
        test_accuracy=accuracy,
        test_precision=precision,
        test_recall=recall,
        test_f1=f1,
        test_roc_auc=roc_auc,
        y_test=y_test,
        y_pred=y_test_pred,
        train_loss_history=history.history.get("loss"),
        val_loss_history=history.history.get("val_loss"),
    )
    logger.info(f"🔍 LSTM verdict: {overfit_report['verdict']} (score={overfit_report['usability_score']})")

    # Persist artifacts
    model_dir = Path(config.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    
    model.save(model_dir / "lstm_model.keras")
    joblib.dump(scaler, model_dir / "lstm_scaler.joblib")
    
    metadata = {
        "model_type": "LSTM",
        "seq_length": seq_length,
        "n_features": len(FEATURE_COLUMNS),
        "decision_threshold": best_threshold,
        "train_accuracy": round(train_accuracy, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "train_samples": int(len(X_train)),
        "val_samples": int(len(X_val)),
        "test_samples": int(len(X_test)),
        "epochs_trained": len(history.history['loss']),
        "training_date": datetime.now().isoformat(),
        "overfitting": overfit_report,
    }
    
    with open(model_dir / "lstm_model.json", "w") as f:
        json.dump(metadata, f, indent=2)
        
    return metadata


def load_lstm_model(config: StockMLConfig) -> Optional[Tuple]:
    """Load the saved model, scaler, and metadata configuration."""
    if not TF_AVAILABLE:
        return None
        
    model_path = config.model_dir / "lstm_model.keras"
    scaler_path = config.model_dir / "lstm_scaler.joblib"
    meta_path = config.model_dir / "lstm_model.json"
    
    if not model_path.exists():
        return None
        
    model = keras_load(model_path)
    scaler = joblib.load(scaler_path) if scaler_path.exists() else None
    
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)
            
    return model, scaler, metadata


def predict_lstm_signal(db: Session, symbol: str, config: StockMLConfig) -> Dict:
    """Generate prediction signal with a symmetric confidence score and deadband."""
    result = load_lstm_model(config)
    if result is None:
        return {"signal": "NO_TRADE", "confidence": 0.0, "reason": "Model uninitialized", "bias": "NEUTRAL"}
    
    model, scaler, metadata = result
    seq_length = metadata.get("seq_length", 20)
    threshold = metadata.get("decision_threshold", 0.50)
    
    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty or len(raw) < seq_length + 10:
        return {"signal": "NO_TRADE", "confidence": 0.0, "reason": "Insufficient candles", "bias": "NEUTRAL"}
    
    features = build_features_from_df(raw, config)
    if features.empty or len(features) < seq_length:
        return {"signal": "NO_TRADE", "confidence": 0.0, "reason": "Feature extraction failed", "bias": "NEUTRAL"}
    
    X_raw = features[FEATURE_COLUMNS].values[-seq_length:]
    X_scaled = scaler.transform(X_raw).reshape(1, seq_length, -1)
    
    prob_up = float(model.predict(X_scaled, verbose=0)[0][0])
    
    # Symmetrical confidence calculation (0.0 to 1.0 scale)
    deadband = 0.04
    if prob_up >= threshold + deadband:
        bias = "BULLISH"
        confidence = (prob_up - threshold) / max(1.0 - threshold, 0.01)
    elif prob_up <= threshold - deadband:
        bias = "BEARISH"
        confidence = (threshold - prob_up) / max(threshold, 0.01)
    else:
        bias = "NEUTRAL"
        confidence = 0.0
        
    confidence = float(np.clip(confidence, 0.0, 1.0))
    signal = bias if confidence >= 0.40 else "NO_TRADE"
    
    return {
        "symbol": symbol,
        "signal": signal,
        "bias": bias,
        "confidence": round(confidence, 3),
        "indicators": {
            "lstm_prob_up": round(prob_up, 4),
            "decision_threshold": threshold
        },
        "reason": f"LSTM prob_up={prob_up:.4f} against threshold={threshold:.3f} (confidence={confidence:.1%})"
    }