# Step 17 – Data-cleaning strategy comparison

## Research method
- Source: `data\processed\travelmind_combined_clusters.csv` (original input preserved).
- Baseline: all coordinate-valid records.
- Conservative: exclude exact placeholder names and records explicitly assessed as `no` for tourism relevance or as `duplicate` in the reviewed sample. Unverified, flagged, and suspected-duplicate records are otherwise retained.
- Strict: exclude every record marked `review_required = yes` in the original data. Unflagged does **not** mean independently verified.
- DBSCAN: haversine metric, eps=2.0 km, min_samples=5.
- K-Means: projected coordinate columns, k=6, random_state=42, n_init=20.
- Each strategy trains new models on its subset; originals are untouched.

## Dataset exclusions
- Conservative: 2 rows excluded.
- Strict: 4523 rows excluded.

## Model comparison
```
    strategy  records  excluded_from_baseline  kmeans_clusters  dbscan_clusters  dbscan_noise  dbscan_coverage_pct  largest_dbscan_cluster_size  largest_cluster_pct_all_records  review_required_remaining  suspected_duplicates_remaining  kmeans_inertia_projected_m2  kmeans_silhouette_sample
    baseline     8590                       0                6              225          2398                72.08                         1265                            14.73                       4523                             450                 1.394299e+13                   0.48255
conservative     8588                       2                6              225          2396                72.10                         1265                            14.73                       4522                             450                 1.394147e+13                   0.48589
      strict     4067                    4523                6              117          1853                54.44                          460                            11.31                          0                               4                 5.761495e+12                   0.45555
```

## Partition stability (ARI on shared attraction IDs)
```
    strategy  shared_records  kmeans_ari_vs_baseline_on_shared_records  dbscan_ari_vs_baseline_on_shared_records
conservative            8588                                   0.99152                                   1.00000
      strict            4067                                   0.70253                                   0.66211
```

## Baseline reproducibility
- K-Means ARI compared with previously saved labels: 1.00000
- DBSCAN ARI compared with previously saved labels: 1.00000

## Interpretation cautions
- Filtering changes density and sample composition; more/fewer clusters is not evidence that one strategy has better tourism relevance.
- ARI measures clustering agreement, not ground-truth tourism accuracy.
- K-Means inertia and sampled silhouette may not be directly compared against historical experiments if inputs, scales, or sample populations differ.
- False negatives are especially possible in strict filtering, because review flags signal uncertainty rather than confirmed errors.
- External attraction verification and duplicate checks are still required.
