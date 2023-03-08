import warnings
from collections.abc import Iterable
from itertools import cycle
from textwrap import wrap
from typing import Optional, Union, Dict, Any

import matplotlib.colors as clr
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as patches
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from matplotlib.collections import PatchCollection
import numpy as np
import pandas as pd

from embedding_annotation.region import Density, Region


def plot_feature(
    feature_names: Any | list[Any],
    df: pd.DataFrame,
    embedding: np.ndarray,
    binary=False,
    s=6,
    alpha=0.1,
    log=False,
    colors=None,
    threshold=0,
    zorder=1,
    title=None,
    ax=None,
    agg="max",
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))

    feature_names = np.atleast_1d(feature_names)
    feature_mask = df.columns.isin(feature_names)

    x = df.values[:, feature_mask]

    if colors is None:
        # colors = ["#fee8c8", "#e34a33"]
        # colors = ["#000000", "#7DF454"]
        colors = ["#000000", "#EA4736"]

    if binary:
        y = np.any(x > threshold, axis=1)
        ax.scatter(
            embedding[~y, 0],
            embedding[~y, 1],
            c=colors[0],
            s=s,
            alpha=alpha,
            rasterized=True,
            zorder=zorder,
        )
        ax.scatter(
            embedding[y, 0],
            embedding[y, 1],
            c=colors[1],
            s=s,
            alpha=alpha,
            rasterized=True,
            zorder=zorder,
        )
    else:
        if agg == "max":
            y = np.max(x, axis=1)
        elif agg == "sum":
            y = np.sum(x, axis=1)
        else:
            raise ValueError(f"Unrecognized aggregator `{agg}`")

        sort_idx = np.argsort(y)  # Trick to make higher values have larger zval

        if log:
            y = np.log1p(y)

        cmap = clr.LinearSegmentedColormap.from_list(
            "expression", [colors[0], colors[1]], N=256
        )
        ax.scatter(
            embedding[sort_idx, 0],
            embedding[sort_idx, 1],
            c=y[sort_idx],
            s=s,
            alpha=alpha,
            rasterized=True,
            cmap=cmap,
            zorder=zorder,
        )

    # Hide ticks and axis
    ax.set_xticks([]), ax.set_yticks([]), ax.axis("equal")

    marker_str = ", ".join(map(str, feature_names))
    if title is None:
        ax.set_title("\n".join(wrap(marker_str, 40)))
    else:
        ax.set_title(title)

    return ax


def plot_features(
    features: list[Any] | dict[str, list[Any]],
    data: pd.DataFrame,
    embedding: np.ndarray,
    per_row=4,
    figwidth=24,
    binary=False,
    s=6,
    alpha=0.1,
    log=False,
    colors=None,
    threshold=0,
    return_ax=False,
    zorder=1,
    agg="max",
):
    n_rows = len(features) // per_row
    if len(features) % per_row > 0:
        n_rows += 1

    figheight = figwidth / per_row * n_rows
    fig, ax = plt.subplots(nrows=n_rows, ncols=per_row, figsize=(figwidth, figheight))

    ax = ax.ravel()

    if isinstance(features, dict):
        features_ = features.values()
    elif isinstance(features, list):
        features_ = features
    else:
        raise ValueError("features cannot be instance of `%s`" % type(features))

    # Handle lists of markers
    all_features = []
    for m in features_:
        if isinstance(m, list):
            for m_ in m:
                all_features.append(m_)
        else:
            all_features.append(m)
    assert all(
        f in data.columns for f in all_features
    ), "One or more of the specified features was not found in dataset"

    if colors is None:
        # colors = ["#fee8c8", "#e34a33"]
        # colors = ["#000000", "#7DF454"]
        colors = ["#000000", "#EA4736"]

    for idx, marker in enumerate(features_):
        plot_feature(
            marker,
            data,
            embedding,
            binary=binary,
            s=s,
            alpha=alpha,
            log=log,
            colors=colors,
            threshold=threshold,
            zorder=zorder,
            ax=ax[idx],
            agg=agg,
        )

        if isinstance(features, dict):
            title = ax.get_title()
            title = f"{list(features)[idx]}\n{title}"
            ax[idx].set_title(title)

        plt.tight_layout()

    # Hide remaining axes
    for idx in range(idx + 1, n_rows * per_row):
        ax[idx].axis("off")

    if return_ax:
        return fig, ax


def get_cmap_colors(cmap: str):
    import matplotlib.cm

    return matplotlib.cm.get_cmap(cmap).colors


def get_cmap_hues(cmap: str):
    """Extract the hue values from a given colormap."""
    colors = get_cmap_colors(cmap)
    hues = [c[0] for c in colors.rgb_to_hsv(colors)]

    return np.array(hues)


def hue_colormap(
    hue: float, levels: Iterable | int = 10, min_saturation: float = 0
) -> colors.ListedColormap:
    """Create an HSV colormap with varying saturation levels"""
    if isinstance(levels, Iterable):
        hsv = [[hue, (s + min_saturation) / (1 + min_saturation), 1] for s in levels]
    else:
        num_levels = len(levels) if isinstance(levels, Iterable) else levels
        hsv = [[hue, s, 1] for s in np.linspace(min_saturation, 1, num=num_levels)]

    rgb = colors.hsv_to_rgb(hsv)
    cmap = colors.ListedColormap(rgb)

    return cmap


def plot_feature_density(
    density: Density,
    embedding: np.ndarray = None,
    levels: int | np.ndarray = 5,
    skip_first: bool = True,
    ax=None,
    cmap="RdBu_r",
    contour_kwargs: dict = {},
    contourf_kwargs: dict = {},
    scatter_kwargs: dict = {},
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))

    tck = None
    if isinstance(levels, Iterable):
        if skip_first:
            levels = levels[1:]
    else:
        if skip_first:
            tck = ticker.MaxNLocator(nbins=levels, prune="lower")

    contour_kwargs_ = {"zorder": 1, "linewidths": 1, "colors": "k", **contour_kwargs}
    contourf_kwargs_ = {"zorder": 1, "alpha": 0.5, **contourf_kwargs}

    x, y, z = density._get_xyz(scaled=True)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        ax.contourf(x, y, z, levels=levels, cmap=cmap, locator=tck, **contourf_kwargs_)
        ax.contour(x, y, z, levels=levels, locator=tck, **contour_kwargs_)

    if embedding is not None:
        scatter_kwargs_ = {
            "zorder": 1,
            "c": "k",
            "s": 6,
            "alpha": 0.1,
        }
        scatter_kwargs_.update(scatter_kwargs)
        ax.scatter(embedding[:, 0], embedding[:, 1], **scatter_kwargs_)

    # Hide ticks and axis
    ax.set_xticks([]), ax.set_yticks([])
    ax.axis("equal")

    return ax


def plot_feature_densities(
    features: list[Any],
    densities: dict[Any, Density],
    embedding: np.ndarray = None,
    levels: int | np.ndarray = 5,
    skip_first: bool = True,
    per_row: int = 4,
    figwidth: int = 24,
    return_ax: bool = False,
    contour_kwargs: dict = {},
    contourf_kwargs: dict = {},
    scatter_kwargs: dict = {},
):
    n_rows = len(features) // per_row
    if len(features) % per_row > 0:
        n_rows += 1

    figheight = figwidth / per_row * n_rows
    fig, ax = plt.subplots(nrows=n_rows, ncols=per_row, figsize=(figwidth, figheight))

    if len(features) == 1:
        ax = np.array([ax])
    ax = ax.ravel()

    for idx, feature in enumerate(features):
        ax[idx].set_title(feature)

        plot_feature_density(
            densities[feature],
            embedding,
            levels=levels,
            skip_first=skip_first,
            ax=ax[idx],
            contour_kwargs=contour_kwargs,
            contourf_kwargs=contourf_kwargs,
            scatter_kwargs=scatter_kwargs,
        )

    # Hide remaining axes
    for idx in range(idx + 1, n_rows * per_row):
        ax[idx].axis("off")

    if return_ax:
        return fig, ax


def plot_region(
    region: Region,
    embedding: np.ndarray = None,
    ax=None,
    fill_color="tab:blue",
    edge_color=None,
    fill_alpha=0.25,
    edge_alpha=1,
    lw=1,
    draw_label=False,
    scatter_kwargs: dict = {},
    label_kwargs: dict = {},
    detail_kwargs: dict = {},
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))

    # If no edge color is specified, use the same color as the fill
    if edge_color is None:
        edge_color = fill_color

    for geom in region.polygon.geoms:
        # Polygon plotting code taken from
        # https://stackoverflow.com/questions/55522395/how-do-i-plot-shapely-polygons-and-objects-using-matplotlib
        path = Path.make_compound_path(
            Path(np.asarray(geom.exterior.coords)[:, :2]),
            *[Path(np.asarray(ring.coords)[:, :2]) for ring in geom.interiors],
        )
        # Fill
        fill_patch = PathPatch(
            path,
            fill=True,
            color=fill_color,
            alpha=fill_alpha,
        )
        ax.add_patch(fill_patch)
        # Boundary
        edge_patch = PathPatch(
            path, fill=False, edgecolor=edge_color, alpha=edge_alpha, lw=lw
        )
        ax.add_patch(edge_patch)

    if draw_label:
        # Draw the lable on the largest polygon in the region
        largest_polygon = max(region.polygon.geoms, key=lambda x: x.area)
        label_kwargs_ = {
            "ha": "center",
            "va": "bottom",
            "fontsize": 12,
            "fontweight": "bold",
        }
        label_kwargs_.update(label_kwargs)
        x, y = largest_polygon.centroid.coords[0]
        label = ax.text(x, y, region.plot_label, **label_kwargs_)
        if region.plot_detail is not None:
            detail_kwargs_ = {
                "ha": "center",
                "va": "top",
                "fontsize": 9,
                "fontweight": "normal",
            }
            detail_kwargs_.update(detail_kwargs)
            label = ax.text(x, y, region.plot_detail, **detail_kwargs_)
        # label.set_bbox(dict(facecolor="white", alpha=0.75, edgecolor="white"))

    if embedding is not None:
        scatter_kwargs_ = {
            "zorder": 1,
            "c": "k",
            "s": 6,
            "alpha": 0.1,
        }
        scatter_kwargs_.update(scatter_kwargs)
        ax.scatter(embedding[:, 0], embedding[:, 1], **scatter_kwargs_)

    # Hide ticks and axis
    ax.set_xticks([]), ax.set_yticks([])
    ax.axis("equal")

    return ax


def plot_regions(
    features: list[Any],
    regions: dict[Any, Region],
    embedding: np.ndarray = None,
    per_row: int = 4,
    figwidth: int = 24,
    return_ax: bool = False,
    fill_color="tab:blue",
    edge_color=None,
    fill_alpha=0.25,
    edge_alpha=1,
    lw=1,
    draw_labels=False,
    scatter_kwargs: dict = {},
    label_kwargs: dict = {},
    detail_kwargs: dict = {},
):
    n_rows = len(regions) // per_row
    if len(regions) % per_row > 0:
        n_rows += 1

    figheight = figwidth / per_row * n_rows
    fig, ax = plt.subplots(nrows=n_rows, ncols=per_row, figsize=(figwidth, figheight))

    if len(regions) == 1:
        ax = np.array([ax])
    ax = ax.ravel()

    for idx, feature in enumerate(features):
        ax[idx].set_title(str(feature))

        plot_region(
            regions[feature],
            embedding,
            ax=ax[idx],
            fill_color=fill_color,
            edge_color=edge_color,
            fill_alpha=fill_alpha,
            edge_alpha=edge_alpha,
            lw=lw,
            draw_label=draw_labels,
            scatter_kwargs=scatter_kwargs,
            label_kwargs=label_kwargs,
            detail_kwargs=detail_kwargs,
        )

    # Hide remaining axes
    for idx in range(idx + 1, n_rows * per_row):
        ax[idx].axis("off")

    if return_ax:
        return fig, ax


def plot_annotation(
    densities: dict[str, Region],
    embedding: np.ndarray,
    cmap: str = "tab10",
    ax=None,
    scatter_kwargs: dict = {},
    label_kwargs: dict = {},
    detail_kwargs: dict = {},
):
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))

    hues = iter(cycle(get_cmap_colors(cmap)))

    for key, density in densities.items():
        plot_region(
            density,
            fill_color=next(hues),
            ax=ax,
            draw_label=True,
            label_kwargs=label_kwargs,
            detail_kwargs=detail_kwargs,
        )

    if embedding is not None:
        scatter_kwargs_ = {
            "zorder": 1,
            "c": "k",
            "s": 6,
            "alpha": 0.1,
            **scatter_kwargs,
        }
        ax.scatter(embedding[:, 0], embedding[:, 1], **scatter_kwargs_)

    # Hide ticks and axis
    ax.set_xticks([]), ax.set_yticks([])
    ax.axis("equal")

    return ax
