"""Build traveller segments from survey responses and write the results the API serves.

Usage:  python -m segmentation.pipeline [responses.csv]

With no argument it uses the synthetic test file. For real responses, download the Google Form's
response sheet as CSV into data/segmentation/ (that folder is excluded from git) and pass its path.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from .clustering import SEED, compare_methods, k_sweep, kmeans
from .describe import TRAITS, describe_segments
from .features import build_features
from .profile_mapping import SHARED_FEATURES
from .survey_schema import Q_DAYS, Q_DISTRICTS, Q_SPEND

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "segmentation" / "SYNTHETIC_tourist_behaviour_619.csv"
OUTPUT_DIR = PROJECT_ROOT / "results" / "segmentation"
PROPOSAL_TARGETS = {"silhouette_min": 0.65, "davies_bouldin_max": 0.80}


def _rounded(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def _write(name, payload):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(json.dumps(_rounded(payload), ensure_ascii=False, indent=1), encoding="utf-8")


def run(input_path=DEFAULT_INPUT):
    input_path = Path(input_path)
    df = pd.read_csv(input_path).dropna(subset=[Q_DAYS, Q_SPEND, Q_DISTRICTS]).reset_index(drop=True)
    synthetic = "data_source" in df and (df["data_source"] == "SYNTHETIC").all()
    planted = df["synthetic_archetype"] if synthetic and "synthetic_archetype" in df else None

    features = build_features(df)
    X = StandardScaler().fit_transform(features)
    methods = compare_methods(df, features, X)

    # The deployed segmentation is K-Means at the k with the best Silhouette score.
    chosen = next(m for m in methods if m["id"] == "kmeans")
    k = chosen["clusters"]
    raw_labels = kmeans(X, k).labels_
    segments = describe_segments(df, features, raw_labels)
    rename = {s["label"]: f"S{i + 1}" for i, s in enumerate(segments)}
    labels = np.array([rename[label] for label in raw_labels])
    for s in segments:
        s["id"] = rename[s.pop("label")]
    meta = {
        "data_source": "synthetic" if synthetic else "survey",
        "input_file": input_path.name,
        "rows": len(df),
        "feature_count": features.shape[1],
        "features": list(features.columns),
        "method": "K-Means",
        "k": k,
        "selection_rule": "K-Means with the number of clusters (2 to 8) that gives the highest Silhouette score",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # Assignment model for website profiles: centres of each segment in the shared-feature space.
    shared = features[SHARED_FEATURES]
    mean, std = shared.mean(), shared.std(ddof=0).replace(0, 1)
    z = (shared - mean) / std
    centres = {sid: z[labels == sid].mean().to_dict() for sid in sorted(set(labels))}
    distances = np.stack([np.sqrt(((z - pd.Series(c)) ** 2).sum(axis=1)) for c in centres.values()], axis=1)
    nearest = np.array(list(centres))[distances.argmin(axis=1)]
    assignment = {"features": SHARED_FEATURES, "mean": mean.to_dict(), "std": std.to_dict(), "centres": centres,
                  "agreement_with_full_model": float((nearest == labels).mean())}

    points = PCA(2, random_state=SEED).fit_transform(X)
    evaluation = {
        "methods": [{k: v for k, v in m.items() if k != "labels"} |
                    ({"agreement_with_planted": float(adjusted_rand_score(planted, m["labels"]))} if planted is not None else {})
                    for m in methods],
        "k_sweep": k_sweep(X, planted),
        "chosen": {"method": "K-Means", "k": k, "silhouette": chosen["silhouette"], "davies_bouldin": chosen["davies_bouldin"],
                   "calinski_harabasz": chosen["calinski_harabasz"]},
        "targets": {**PROPOSAL_TARGETS,
                    "silhouette_met": chosen["silhouette"] >= PROPOSAL_TARGETS["silhouette_min"],
                    "davies_bouldin_met": chosen["davies_bouldin"] <= PROPOSAL_TARGETS["davies_bouldin_max"]},
        "assignment_agreement": assignment["agreement_with_full_model"],
    }

    _write("segments.json", {"meta": meta, "traits": [{"key": k_, "label": l, "unit": u} for k_, l, u in TRAITS], "segments": segments})
    _write("evaluation.json", {"meta": meta, **evaluation})
    _write("points.json", {"meta": meta, "points": [{"x": float(x), "y": float(y), "segment": s} for (x, y), s in zip(points, labels)]})
    _write("assignment.json", {"meta": meta, **assignment})
    return meta, segments, evaluation


def main():
    meta, segments, evaluation = run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT)
    print(f"{meta['rows']} rows ({meta['data_source']}), {meta['feature_count']} features, K-Means k={meta['k']}")
    for s in segments:
        print(f"  {s['id']}  {s['name']:<40} {s['size']:>4} rows  {s['description']}")
    print(f"Silhouette {evaluation['chosen']['silhouette']:.3f} (target {PROPOSAL_TARGETS['silhouette_min']}), "
          f"profile assignment agrees with the full model on {evaluation['assignment_agreement']:.0%} of rows")
    print(f"Results written to {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
