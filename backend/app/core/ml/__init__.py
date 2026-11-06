from app.core.ml.config import StockMLConfig

__all__ = ["StockMLConfig"]


def train_stock_model(*args, **kwargs):
    from app.core.ml.stock_model import train_stock_model as _fn
    return _fn(*args, **kwargs)


def predict_stock_signal(*args, **kwargs):
    from app.core.ml.stock_model import predict_stock_signal as _fn
    return _fn(*args, **kwargs)
