"""Run the three clustering algorithms and the two baselines, and score them."""
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score,
                             silhouette_score)
from sklearn.preprocessing import StandardScaler

from .survey_schema import AGES, Q_AGE, Q_COUNTRY

SEED = 42
K_RANGE = range(2, 9)
DBSCAN_EPS = np.arange(2.5, 6.01, 0.25)
DBSCAN_MIN_SAMPLES = (5, 10)
DBSCAN_MAX_NOISE = 0.25


def scores(X, labels):
    """Silhouette, Davies-Bouldin and Calinski-Harabasz, ignoring DBSCAN noise points."""
    keep = labels != -1
    if len(set(labels[keep])) < 2:
        return None
    return (float(silhouette_score(X[keep], labels[keep])), float(davies_bouldin_score(X[keep], labels[keep])),
            float(calinski_harabasz_score(X[keep], labels[keep])))


def best_by_silhouette(X, candidates):
    """Pick the (name, labels) candidate with the highest Silhouette score."""
    scored = [(scores(X, labels), name, labels) for name, labels in candidates]
    scored = [s for s in scored if s[0] is not None]
    return max(scored, key=lambda s: s[0][0])


def kmeans(X, k):
    return KMeans(k, n_init=10, random_state=SEED).fit(X)


def compare_methods(df, features, X):
    """Baselines 1 and 2 from the proposal, then K-Means, Agglomerative and DBSCAN, each at its best setting."""
    age3 = df[Q_AGE].map(lambda a: "<25" if a == AGES[0] else "25-45" if a in AGES[1:3] else ">45")
    spend_only = StandardScaler().fit_transform(features[["spend_band"]])
    methods = []

    def add(method_id, name, labels, setting, kind):
        sil, dbi, ch = scores(X, labels)
        methods.append({"id": method_id, "name": name, "kind": kind, "setting": setting,
                        "clusters": int(len(set(labels) - {-1})), "noise_share": float((labels == -1).mean()),
                        "silhouette": sil, "davies_bouldin": dbi, "calinski_harabasz": ch, "labels": labels})

    add("baseline_demographic", "Baseline 1: age band and country", pd.factorize(age3 + " | " + df[Q_COUNTRY])[0],
        "3 age bands x country", "baseline")
    _, k, labels = best_by_silhouette(spend_only, [(k, kmeans(spend_only, k).labels_) for k in range(2, 6)])
    add("baseline_spending", "Baseline 2: K-Means on spending only", labels, f"k={k}", "baseline")
    _, k, labels = best_by_silhouette(X, [(k, kmeans(X, k).labels_) for k in K_RANGE])
    add("kmeans", "K-Means", labels, f"k={k}", "proposed")
    _, k, labels = best_by_silhouette(X, [(k, AgglomerativeClustering(k, linkage="ward").fit_predict(X)) for k in K_RANGE])
    add("agglomerative", "Agglomerative (Ward)", labels, f"k={k}", "proposed")
    candidates = []
    for eps in DBSCAN_EPS:
        for min_samples in DBSCAN_MIN_SAMPLES:
            labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)
            if (labels == -1).mean() <= DBSCAN_MAX_NOISE:
                candidates.append((f"eps={eps:.2f}, min_samples={min_samples}", labels))
    if candidates:
        _, setting, labels = best_by_silhouette(X, candidates)
        add("dbscan", "DBSCAN", labels, setting, "proposed")
    return methods


def k_sweep(X, planted=None):
    """K-Means scores for every k, plus agreement with planted groups when the data is synthetic."""
    rows = []
    for k in K_RANGE:
        labels = kmeans(X, k).labels_
        sil, dbi, ch = scores(X, labels)
        row = {"k": k, "silhouette": sil, "davies_bouldin": dbi, "calinski_harabasz": ch}
        if planted is not None:
            row["agreement_with_planted"] = float(adjusted_rand_score(planted, labels))
        rows.append(row)
    return rows
