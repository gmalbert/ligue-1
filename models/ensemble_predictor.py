"""Ensemble model definition for Ligue Odds.

Provides create_ensemble_model() — a soft-voting VotingClassifier with
XGBoost, Random Forest, Gradient Boosting, and Logistic Regression.

Weights: XGB=2, RF=1.5, GB=1, LR=0.5 (higher weight → higher influence).
predict_proba column order (alphabetical LabelEncoder): [A=0, D=1, H=2]
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


class MarketBlendModel:
    """Blend model probabilities with market-implied probabilities.

    ``market_weight`` is chosen on validation data. A value of 0 uses only the
    trained model; 1 uses only the bookmaker-implied probabilities.
    """

    def __init__(
        self,
        base_model: VotingClassifier,
        feature_names: list[str],
        market_weight: float = 0.0,
    ) -> None:
        self.base_model = base_model
        self.feature_names = feature_names
        self.market_weight = float(market_weight)
        self.classes_ = getattr(base_model, "classes_", np.array([0, 1, 2]))

    @property
    def named_estimators_(self):
        return getattr(self.base_model, "named_estimators_", {})

    def _market_proba(self, X) -> np.ndarray | None:
        idx = {
            name: self.feature_names.index(name)
            for name in [
                "ImpliedProb_AwayWin",
                "ImpliedProb_Draw",
                "ImpliedProb_HomeWin",
            ]
            if name in self.feature_names
        }
        if len(idx) != 3:
            return None
        market = np.column_stack([
            X[:, idx["ImpliedProb_AwayWin"]],
            X[:, idx["ImpliedProb_Draw"]],
            X[:, idx["ImpliedProb_HomeWin"]],
        ]).astype(float)
        market = np.clip(market, 1e-6, 1.0)
        return market / market.sum(axis=1, keepdims=True)

    def predict_proba(self, X) -> np.ndarray:
        X_arr = np.asarray(X)
        model_proba = self.base_model.predict_proba(X_arr)
        model_proba = model_proba / model_proba.sum(axis=1, keepdims=True)
        market_proba = self._market_proba(X_arr)
        if market_proba is None or self.market_weight <= 0:
            return model_proba
        blended = (1 - self.market_weight) * model_proba + self.market_weight * market_proba
        return blended / blended.sum(axis=1, keepdims=True)

    def predict(self, X) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)


def create_ensemble_model(xgb_params: dict | None = None) -> VotingClassifier:
    """Return an unfitted soft-voting ensemble.

    Parameters
    ----------
    xgb_params : optional dict of XGBoost hyperparameters to override defaults.
                 Typically loaded from models/best_hyperparams.json after an
                 --optimize run.
    """
    defaults = dict(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )
    if xgb_params:
        defaults.update(xgb_params)
    xgb = XGBClassifier(**defaults)
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    gb = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=5,
        random_state=42,
    )
    lr = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            max_iter=3000,
            random_state=42,
            class_weight="balanced",
        ),
    )

    return VotingClassifier(
        estimators=[("xgb", xgb), ("rf", rf), ("gb", gb), ("lr", lr)],
        voting="soft",
        weights=[2, 1.5, 1, 0.5],
    )


def save_model(model: VotingClassifier, path: str = "models/ensemble_model.pkl") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)


def load_model(path: str = "models/ensemble_model.pkl") -> VotingClassifier:
    with open(path, "rb") as f:
        return pickle.load(f)
