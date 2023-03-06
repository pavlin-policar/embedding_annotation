from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from KDEpy import FFTKDE
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn import neighbors

import embedding_annotation.graph as g
from embedding_annotation.data import Variable
from embedding_annotation.metrics import (
    _dict_pdist,
    intersection_over_union,
    intersection_over_union_dist,
    intersection_percentage,
)
from embedding_annotation.region import Density, Region, CompositeRegion


def feature_merge_candidates(features, adj, merge_threshold=0.05):
    import embedding_annotation as annotate

    feature_vars = features.columns.tolist()

    scores = annotate.fs._morans_i(features.values, adj)
    feature_scores = dict(zip(feature_vars, scores))

    candidates = []
    for i in range(len(feature_vars)):
        for j in range(i + 1, len(feature_vars)):
            f1, f2 = feature_vars[i], feature_vars[j]
            if not f1.can_merge_with(f2):
                continue

            # The values should all be binary, one-hot encoded values, so we can
            # just add them up
            new_values = np.maximum(features[f1], features[f2])
            new_score = annotate.fs._morans_i(new_values, adj)
            gain = new_score / (feature_scores[f1] + feature_scores[f2]) - 1
            candidates.append({"feature_1": f1, "feature_2": f2, "moran_gain": gain})

    # If a feature is to be merged with more than one variable, allow only a
    # single merge. Pick the merge with the largest Moran gain
    candidates = candidates.sort_values("moran_gain", ascending=False)

    seen, idx_to_drop = set(), []
    for idx, row in candidates.iterrows():
        pair = frozenset([row["feature_1"], row["feature_2"]])
        if any(len(pair & s) > 0 for s in seen):
            idx_to_drop.append(idx)
        else:
            seen.add(pair)
    candidates.drop(index=idx_to_drop, inplace=True)

    # Keep only the candidas above the merge threshold
    candidates = candidates[candidates["moran_gain"] >= merge_threshold]

    return candidates.reset_index(drop=True)


def feature_merge(features: pd.DataFrame, embedding: np.ndarray, scale: float, merge_threshold: float = 0.05):
    # adj = radius_neighbors_graph(
    #     embedding, radius=scale, metric="euclidean", include_self=False, n_jobs=8
    # )
    #
    # # Symmetrize matrix
    # adj = adj.astype(bool)
    # adj = adj + adj.T
    # adj = adj.astype(int)

    # Create copy, we don't want to modify the original list
    features = features.copy()

    def _feature_merge(merge_features: tuple[Any, Any]):
        """Merge all the regions in the list of tuples."""
        # Sometimes, a feature should be merged more than once, so we can't
        # remove it immediately after merge
        features_to_remove = set()
        for f1, f2 in merge_features:
            features[f1.merge_with(f2)] = np.maximum(features[f1], features[f2])
            features_to_remove.update([f1, f2])

        features.drop(columns=features_to_remove, inplace=True)

    while (
        merge_features := feature_merge_candidates(features, adj, merge_threshold)
    ).shape[0] > 0:
        _feature_merge(
            merge_features[["feature_1", "feature_2"]].itertuples(index=False)
        )

    return features


def estimate_feature_densities(
    features: list[Any],
    feature_matrix: pd.DataFrame,
    embedding: np.ndarray,
    log: bool = False,
    n_grid_points: int = 100,
    kernel: str = "gaussian",
    bw: float = 1,
) -> dict[Any, Density]:
    densities = {}

    for feature in features:
        x = feature_matrix[feature].values
        if log:
            x = np.log1p(x)

        kde = FFTKDE(kernel=kernel, bw=bw).fit(embedding, weights=x)
        grid, points = kde.evaluate(n_grid_points)

        densities[feature] = Density(grid, points)

    return densities


def find_regions(
    densities: dict[Variable, Density],
    level: float = 0.25,
) -> dict[Any, Region]:
    """Identify regions for each feature at a specified contour level."""
    return {
        variable: Region(variable, density, level=level)
        for variable, density in densities.items()
    }


def stage_1_merge_candidates(
    regions: dict[Any, Region],
    overlap_threshold: float = 0.75,
) -> pd.DataFrame:
    region_keys = list(regions.keys())
    region_values = list(regions.values())

    result = []
    for i in range(len(region_values)):
        for j in range(i + 1, len(region_values)):
            r1, r2 = region_values[i], region_values[j]
            if not r1.feature.can_merge_with(r2.feature):
                continue

            p1, p2 = r1.polygon, r2.polygon

            overlap_ij = p1.intersection(p2).area / p1.area
            overlap_ji = p2.intersection(p1).area / p2.area
            overlap = max(overlap_ij, overlap_ji)

            result.append(
                {
                    "feature_1": region_keys[i],
                    "feature_2": region_keys[j],
                    "overlap": overlap,
                }
            )

    df = pd.DataFrame(result)
    if len(df):
        df = df.loc[df["overlap"] >= overlap_threshold]
    return df


def stage_1_merge_regions(
    regions: dict[Any, Region],
    merge_features: pd.DataFrame = None,
    overlap_threshold: float = 0.75,
) -> list[Region]:
    """

    Parameters
    ----------
    regions: list[Region]
        The regions to be merged. This list can contain regions that should not
        be merged as well.
    merge_features
    overlap_threshold: float
        If merge candidates are provided, this value is ignored.

    Returns
    -------
    list[Region]
        A new list of regions, where similar regions have been merged.
    """
    # Create copy, we don't want to modify the original list
    regions = dict(regions)

    def _merge_regions(merge_features: tuple[Any, Any]):
        """Merge all the regions in the list of tuples."""
        # Sometimes, a feature should be merged more than once, so we can't
        # remove it immediately after merge
        features_to_remove = set()
        for f1, f2 in merge_features:
            r1, r2 = regions[f1], regions[f2]
            new_region = Region(
                r1.feature.merge_with(r2.feature), r1.density + r2.density
            )
            features_to_remove.update([f1, f2])
            regions[new_region.feature] = new_region

        for feature in features_to_remove:
            del regions[feature]

    if merge_features is not None:
        if isinstance(merge_features, pd.DataFrame):
            merge_features = merge_features[["feature_1", "feature_2"]].itertuples(
                index=False
            )
        _merge_regions(merge_features)
    else:
        while (
            merge_features := stage_1_merge_candidates(regions, overlap_threshold)
        ).shape[0] > 0:
            _merge_regions(
                merge_features[["feature_1", "feature_2"]].itertuples(index=False)
            )

    return regions


def group_similar_features(
    features: list[Any],
    regions: dict[Any, Region],
    threshold: float = 0.9,
    method: str = "max-cliques",
):
    # We only care about the regions that appear in the feature list
    regions = {k: d for k, d in regions.items() if k in features}

    # Create a similarity weighted graph with edges appearing only if they have
    # IoU > threshold
    distances = _dict_pdist(regions, intersection_over_union)
    graph = g.similarities_to_graph(distances, threshold=threshold)
    node_labels = dict(enumerate(regions.keys()))
    graph = g.label_nodes(graph, node_labels)

    # Once we construct the graph, find the max-cliques. These will serve as our
    # merged "clusters"
    if method == "max-cliques":
        cliques = g.max_cliques(graph)
        clusts = {f"Cluster {cid}": vs for cid, vs in enumerate(cliques, start=1)}
    elif method == "connected-components":
        connected_components = g.connected_components(graph)
        clusts = {
            f"Cluster {cid}": list(c)
            for cid, c in enumerate(connected_components, start=1)
        }
    else:
        raise ValueError(
            f"Unrecognized method `{method}`. Can be one of `max-cliques`, "
            f"`connected-components`"
        )

    clust_densities = {
        cid: CompositeRegion(
            feature=cid, regions=[d for d in regions.values() if d.feature in features]
        )
        for cid, features in clusts.items()
    }

    return clusts, clust_densities


def group_similar_features_dendrogram(
    features: list,
    densities: pd.DataFrame,
    threshold: float = 0.1,
    plot_dendrogram: bool = False,
):
    # We only care about the densities that appear in the feature list
    densities = {k: d for k, d in densities.items() if k in features}

    # Perform complete-linkage hierarchical clustering to ensure that all the
    # features have at most the specified threshold distance between them
    distances = _dict_pdist(densities, intersection_over_union_dist)
    Z = linkage(distances, method="complete")
    cluster_assignment = fcluster(Z, t=threshold, criterion="distance")
    cluster_assignment = cluster_assignment - 1  # clusters from linkage start at 1

    # Re-label the clusters so clusters with more elements come first
    cluster_counts = Counter(cluster_assignment)
    cluster_mapping = {k: i for i, (k, _) in enumerate(cluster_counts.most_common())}
    cluster_assignment = np.array([cluster_mapping[c] for c in cluster_assignment])

    if plot_dendrogram:
        import matplotlib.pyplot as plt
        from scipy.cluster.hierarchy import dendrogram

        fig = plt.figure(figsize=(24, 6))
        dendrogram(Z, color_threshold=threshold)
        ax = fig.get_axes()[0]
        ax.axhline(threshold, linestyle="dashed", c="k")

    clusts = {
        f"Cluster {cid}": np.array(features)[cluster_assignment == cid].tolist()
        for cid in np.unique(cluster_assignment)
    }

    clust_densities = {
        cid: CompositeRegion(
            feature=cid,
            regions=[d for d in densities.values() if d.feature in features],
        )
        for cid, features in clusts.items()
    }

    return clusts, clust_densities


def optimize_layout(
    regions: dict[Any, Region], max_overlap: float = 0.05
) -> list[list[Any]]:
    density_names = list(regions.keys())

    overlap = _dict_pdist(regions, intersection_percentage)
    graph = g.similarities_to_graph(overlap, threshold=max_overlap)
    node_labels = dict(enumerate(density_names))
    graph = g.label_nodes(graph, node_labels)

    independent_sets = g.independent_sets(graph)

    return independent_sets


def kth_median_distance(x: np.ndarray, k_neighbors: int):
    """Find the median distance of each point's k-th nearest neighbor."""
    nn = neighbors.NearestNeighbors(n_neighbors=k_neighbors)
    nn.fit(x)
    distances, indices = nn.kneighbors()

    return np.median(distances[:, -1])
