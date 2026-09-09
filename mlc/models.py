from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import Normalizer
from sklearn.svm import LinearSVC

from .config import LABEL_NAMES, PRESENT, RANDOM_SEED
from .rules import apply_rules, rule_feature_vector

RANDOM_STATE = RANDOM_SEED

def make_tfidf() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                 min_df=2, sublinear_tf=True, lowercase=True,
                                 strip_accents=None, token_pattern=r"(?u)\b\w[\w\-/µμ°+]*\b")),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                 min_df=3, sublinear_tf=True, lowercase=True)),
    ])

class RuleFeatures:

    def __init__(self) -> None:
        self.dv = DictVectorizer(sparse=True)

    def fit(self, texts: Sequence[str], y=None) -> "RuleFeatures":
        self.dv.fit([rule_feature_vector(t) for t in texts])
        return self

    def transform(self, texts: Sequence[str]):
        return self.dv.transform([rule_feature_vector(t) for t in texts])

    def fit_transform(self, texts: Sequence[str], y=None):
        return self.fit(texts).transform(texts)

    def get_feature_names_out(self, *a):
        return np.asarray(self.dv.get_feature_names_out())

@dataclass
class MajorityBaseline:
    name: str = "majority"
    majority_: List[int] = field(default_factory=list)

    def fit(self, texts, Y, mask=None):
        Y = np.asarray(Y)
        mask = np.ones_like(Y, dtype=bool) if mask is None else np.asarray(mask,
                                                                          dtype=bool)
        self.majority_ = []
        for j in range(Y.shape[1]):
            yj = Y[mask[:, j], j]
            n_pos = int((yj == 1).sum())
            self.majority_.append(1 if len(yj) and n_pos * 2 >= len(yj) else 0)
        return self

    def predict(self, texts):
        return np.tile(np.asarray(self.majority_), (len(texts), 1))

    def predict_proba(self, texts):
        return self.predict(texts).astype(float)

@dataclass
class AllPositiveBaseline:

    name: str = "all_positive"

    def fit(self, texts=None, Y=None, mask=None):
        return self

    def predict(self, texts):
        return np.ones((len(texts), len(LABEL_NAMES)), dtype=int)

    def predict_proba(self, texts):
        return self.predict(texts).astype(float)

@dataclass
class RuleModel:
    name: str = "rules"

    def fit(self, texts=None, Y=None, mask=None):
        return self

    def predict(self, texts):
        out = np.zeros((len(texts), len(LABEL_NAMES)), dtype=int)
        for i, t in enumerate(texts):
            labels = apply_rules(t, allow_unclear=False).labels
            for j, lb in enumerate(LABEL_NAMES):
                out[i, j] = 1 if labels[lb] == PRESENT else 0
        return out

    def predict_proba(self, texts):
        return self.predict(texts).astype(float)

class OvRLinear:

    def __init__(self, name: str, feature_kind: str = "tfidf",
                 estimator: str = "lr", C: float = 4.0,
                 class_weight: Optional[str] = "balanced") -> None:
        self.name = name
        self.feature_kind = feature_kind
        self.estimator = estimator
        self.C = C
        self.class_weight = class_weight
        self.vec_: Any = None
        self.models_: List[Any] = []
        self.constant_: List[Optional[int]] = []
        self.thresholds_: Optional[np.ndarray] = None

    def set_thresholds(self, thresholds) -> "OvRLinear":
        self.thresholds_ = np.asarray(thresholds, dtype=float)
        return self

    def _build_vectoriser(self):
        if self.feature_kind == "tfidf":
            return make_tfidf()
        if self.feature_kind == "rulefeat":
            return RuleFeatures()
        if self.feature_kind == "hybrid":
            return _Hybrid()
        if self.feature_kind == "lsa":
            return _LSA()
        raise ValueError(self.feature_kind)

    def _new_estimator(self):
        if self.estimator == "lr":
            return LogisticRegression(C=self.C, max_iter=3000,
                                      class_weight=self.class_weight,
                                      random_state=RANDOM_STATE)
        if self.estimator == "svm":
            return LinearSVC(C=self.C, class_weight=self.class_weight,
                             random_state=RANDOM_STATE, max_iter=20000)
        raise ValueError(self.estimator)

    def fit(self, texts, Y, mask=None):
        Y = np.asarray(Y)
        mask = np.ones_like(Y, dtype=bool) if mask is None else np.asarray(mask)
        self.vec_ = self._build_vectoriser()
        X = self.vec_.fit_transform(list(texts))
        self.models_, self.constant_ = [], []
        for j in range(Y.shape[1]):
            keep = mask[:, j]
            yj = Y[keep, j]
            if len(set(yj.tolist())) < 2:
                self.models_.append(None)
                self.constant_.append(int(yj[0]) if len(yj) else 0)
                continue
            est = self._new_estimator().fit(X[keep], yj)
            self.models_.append(est)
            self.constant_.append(None)
        return self

    def predict(self, texts):
        if self.thresholds_ is not None:
            P = self.predict_proba(texts)
            return (P >= self.thresholds_[None, :]).astype(int)
        X = self.vec_.transform(list(texts))
        out = np.zeros((len(texts), len(self.models_)), dtype=int)
        for j, est in enumerate(self.models_):
            out[:, j] = self.constant_[j] if est is None else est.predict(X)
        return out

    def predict_proba(self, texts):
        X = self.vec_.transform(list(texts))
        out = np.zeros((len(texts), len(self.models_)), dtype=float)
        for j, est in enumerate(self.models_):
            if est is None:
                out[:, j] = float(self.constant_[j])
            elif hasattr(est, "predict_proba"):
                out[:, j] = est.predict_proba(X)[:, 1]
            else:
                d = est.decision_function(X)
                out[:, j] = 1.0 / (1.0 + np.exp(-d))
        return out


class _Hybrid:
    def __init__(self) -> None:
        self.tfidf = make_tfidf()
        self.rules = RuleFeatures()

    def fit_transform(self, texts, y=None):
        a = self.tfidf.fit_transform(texts)
        b = self.rules.fit_transform(texts)
        return sparse.hstack([a, b]).tocsr()

    def transform(self, texts):
        return sparse.hstack([self.tfidf.transform(texts),
                              self.rules.transform(texts)]).tocsr()

    def get_feature_names_out(self, *a):
        return np.concatenate([np.asarray(self.tfidf.get_feature_names_out()),
                               self.rules.get_feature_names_out()])

class _LSA:

    def __init__(self, n_components: int = 180) -> None:
        self.n_components = n_components
        self.tfidf = make_tfidf()
        self.svd = None
        self.norm = None

    def fit_transform(self, texts, y=None):
        X = self.tfidf.fit_transform(list(texts))
        k = int(min(self.n_components, max(2, min(X.shape) - 1)))
        self.svd = TruncatedSVD(n_components=k, random_state=RANDOM_STATE)
        self.norm = Normalizer(copy=False)
        return self.norm.fit_transform(self.svd.fit_transform(X))

    def transform(self, texts):
        X = self.tfidf.transform(list(texts))
        return self.norm.transform(self.svd.transform(X))

    def get_feature_names_out(self, *a):
        k = self.svd.n_components if self.svd is not None else self.n_components
        return np.asarray([f"lsa_{i}" for i in range(k)])

LADDER = ("majority", "all_positive", "rules", "tfidf_lr", "tfidf_svm",
          "lsa_lr", "rulefeat_lr", "hybrid_lr")

def build_model_zoo(thresholds: Optional[Dict[str, np.ndarray]] = None
                    ) -> Dict[str, Any]:
    zoo: Dict[str, Any] = {
        "majority": MajorityBaseline(),
        "all_positive": AllPositiveBaseline(),
        "rules": RuleModel(),
        "tfidf_lr": OvRLinear("tfidf_lr", "tfidf", "lr", C=4.0),
        "tfidf_svm": OvRLinear("tfidf_svm", "tfidf", "svm", C=0.5),
        "lsa_lr": OvRLinear("lsa_lr", "lsa", "lr", C=4.0),
        "rulefeat_lr": OvRLinear("rulefeat_lr", "rulefeat", "lr", C=4.0),
        "hybrid_lr": OvRLinear("hybrid_lr", "hybrid", "lr", C=4.0),
    }
    if thresholds:
        for name, th in thresholds.items():
            if name in zoo and hasattr(zoo[name], "set_thresholds"):
                zoo[name].set_thresholds(th)
    return zoo

def tune_thresholds(model: Any, texts: Sequence[str], Y, mask=None,
                    grid: Sequence[float] = tuple(np.arange(0.05, 0.96, 0.05))
                    ) -> np.ndarray:
    Y = np.asarray(Y)
    mask = np.ones_like(Y, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    P = model.predict_proba(list(texts))
    out = np.full(Y.shape[1], 0.5, dtype=float)
    for j in range(Y.shape[1]):
        keep = mask[:, j]
        if keep.sum() == 0:
            continue
        y, p = Y[keep, j], P[keep, j]
        best_t, best_f = 0.5, -1.0
        for t in grid:
            pred = (p >= t).astype(int)
            tp = int(((y == 1) & (pred == 1)).sum())
            fp = int(((y == 0) & (pred == 1)).sum())
            fn = int(((y == 1) & (pred == 0)).sum())
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            if f > best_f:
                best_t, best_f = float(t), f
        out[j] = best_t
    return out
