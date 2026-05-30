"""Neural network predictor for Ligue Odds.

3-layer fully connected network with batch normalisation and dropout,
trained on the same FEATURE_COLS as the ensemble model.

Outputs:
    models/nn_model.pt      — trained LaLigaNet weights
    models/nn_scaler.pkl    — fitted StandardScaler

Usage (called from train_models.py):
    from models.nn_predictor import train_nn, load_nn, predict_nn
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ── Architecture ───────────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class LaLigaNet(nn.Module):
        """3-layer fully connected network for 3-class match outcome prediction."""

        def __init__(self, input_dim: int, dropout: float = 0.3):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 128),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(128, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, 3),   # logits: [Away Win, Draw, Home Win]
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.net(x)


# ── Training ──────────────────────────────────────────────────────────────

def train_nn(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 80,
    batch_size: int = 256,
    lr: float = 1e-3,
    model_path: str = "models/nn_model.pt",
    scaler_path: str = "models/nn_scaler.pkl",
) -> dict:
    """Train LaLigaNet, save weights + scaler, return test metrics.

    Returns
    -------
    dict with keys: accuracy, f1_macro, log_loss (or a stub if torch not available)
    """
    if not TORCH_AVAILABLE:
        print("  ⚠ PyTorch not installed — skipping neural network training.")
        return {"accuracy": 0.0, "f1_macro": 0.0, "log_loss": 0.0, "skipped": True}

    from sklearn.metrics import accuracy_score, f1_score, log_loss

    # Scale features
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train.astype(np.float32))
    X_test_s  = scaler.transform(X_test.astype(np.float32))

    # Save scaler
    Path(scaler_path).parent.mkdir(parents=True, exist_ok=True)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    # Tensors
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    X_tr = torch.tensor(X_train_s, dtype=torch.float32).to(device)
    y_tr = torch.tensor(y_train,   dtype=torch.long).to(device)
    X_te = torch.tensor(X_test_s,  dtype=torch.float32).to(device)

    dataset = TensorDataset(X_tr, y_tr)
    loader  = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)

    input_dim = X_train.shape[1]
    model = LaLigaNet(input_dim).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=lr * 10, steps_per_epoch=max(1, len(loader)), epochs=epochs
    )
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(epochs):
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            scheduler.step()

    # Evaluate
    model.eval()
    with torch.no_grad():
        logits   = model(X_te)
        probs    = torch.softmax(logits, dim=1).cpu().numpy()
        y_pred   = np.argmax(probs, axis=1)

    from sklearn.metrics import accuracy_score, f1_score, log_loss  # noqa: F811
    metrics = {
        "accuracy":  round(float(accuracy_score(y_test, y_pred)), 4),
        "f1_macro":  round(float(f1_score(y_test, y_pred, average="macro")), 4),
        "log_loss":  round(float(log_loss(y_test, probs)), 4),
    }

    # Save model weights
    torch.save({"state_dict": model.state_dict(), "input_dim": input_dim}, model_path)
    print(
        f"  NN Accuracy: {metrics['accuracy']:.1%}  |"
        f"  F1: {metrics['f1_macro']:.3f}  |"
        f"  Log Loss: {metrics['log_loss']:.3f}"
    )
    print(f"  Saved: {model_path} + {scaler_path}")
    return metrics


# ── Inference ─────────────────────────────────────────────────────────────

def load_nn(
    model_path: str = "models/nn_model.pt",
    scaler_path: str = "models/nn_scaler.pkl",
) -> Tuple["LaLigaNet", "StandardScaler"] | Tuple[None, None]:
    """Load a saved LaLigaNet and its scaler. Returns (None, None) if unavailable."""
    if not TORCH_AVAILABLE:
        return None, None
    if not Path(model_path).exists() or not Path(scaler_path).exists():
        return None, None

    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)

    ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
    input_dim = ckpt["input_dim"]
    net = LaLigaNet(input_dim)
    net.load_state_dict(ckpt["state_dict"])
    net.eval()
    return net, scaler


def predict_nn(
    X: np.ndarray,
    model: "LaLigaNet",
    scaler: "StandardScaler",
) -> np.ndarray:
    """Return probability matrix shape (n_samples, 3) — [P(Away), P(Draw), P(Home)]."""
    if not TORCH_AVAILABLE or model is None:
        raise RuntimeError("PyTorch model not available.")

    X_s = scaler.transform(X.astype(np.float32))
    X_t = torch.tensor(X_s, dtype=torch.float32)

    with torch.no_grad():
        logits = model(X_t)
        probs  = torch.softmax(logits, dim=1).numpy()

    return probs
