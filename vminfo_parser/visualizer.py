import logging
import math
import re
import typing as t
from collections.abc import Callable, Iterable
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.figure import Figure
from matplotlib.typing import ColorType

from . import config, const

LOGGER = logging.getLogger(__name__)

# Visualize method → PNG report slug. Disk-space methods share two reports; see _report_name.
_GRAPH_METHOD_NAMES = {
    "visualize_os_distribution": "get-os-counts",
    "visualize_granular_os_distribution": "get-granular-os-counts",
    "visualize_supported_os_distribution": "get-supported-os",
    "visualize_unsupported_os_distribution": "get-unsupported-os",
    "visualize_os_version_distribution": "output-os-by-version",
}


# Parameter Specification for methods that use the plotter decorator
# NOTE: VSCode Pylance extention does not properly display type hints for ParamSpec
#       but it didnt handle functools.wraps properly either, so no loss by switching to new standard
PlotterParam = t.ParamSpec("PlotterParam")


def plotter(func: Callable[PlotterParam, None]) -> Callable[PlotterParam, Figure | None]:
    """Decorate functions that use matplotlib.pyplot to create graphs.

    Allows for different output methods depending on external variables.
    Returns the figure in testing, writes PNG files when graph_output_dir is set,
    otherwise shows the figure interactively.

    Note:
        This decorator expects the wrapped function to be an instance method on
        Visualizer (i.e. ``args[0]`` is ``self``).  It reads ``self.config`` to
        determine the output directory and report name.

    Args:
        func (Callable[PlotterParam, None]): Function or Method being wrapped

    Returns:
        Callable[PlotterParam, Figure] | None: Wrapped Funciton or Method
    """

    def plot_wrapper(
        *args: PlotterParam.args,
        **kwargs: PlotterParam.kwargs,
    ) -> Figure | None:
        """Wrap plotter fuction to enable configured output.

        Returns:
            plt.Figure | None: Figure from current matplotlib canvas if in testing. Defaults to None
        """
        data: pd.DataFrame | pd.Series | None = None
        for arg in args:
            if isinstance(arg, pd.DataFrame | pd.Series):
                data = arg
                break
        else:
            for value in kwargs.values():
                if isinstance(value, pd.DataFrame | pd.Series):
                    data = value
                    break

        if data is None or data.empty:
            LOGGER.warning("No data to graph")
            return None
        func(*args, **kwargs)
        figure = plt.gcf()
        if config._IS_TEST:
            return figure

        output_dir = _graph_output_dir(args)
        if output_dir is not None:
            path = _unique_graph_path(output_dir, _graph_filename(func, args, kwargs))
            figure.savefig(path, bbox_inches="tight")
            LOGGER.info("Wrote graph to %s", path)
            plt.close()
            return None

        plt.show(block=True)
        plt.close()
        return None

    return plot_wrapper


def _slug(value: str) -> str:
    """Turn a report or OS label into a filesystem-safe filename fragment."""
    slug = re.sub(r"[^\w]+", "-", value.strip())
    return slug.strip("-") or "unknown"


def _report_name(
    visualize_method: Callable[..., object],
    parser_config: config.Config | None,
    kwargs: dict[str, object],
) -> str:
    """PNG slug for the visualize method being called, not the first enabled CLI flag."""
    method_name = getattr(visualize_method, "__name__", "")
    mapped = _GRAPH_METHOD_NAMES.get(method_name)
    if mapped:
        return mapped
    if method_name in {"visualize_disk_space_horizontal", "visualize_disk_space_vertical"}:
        os_label = kwargs.get("os_filter") or kwargs.get("os_name")
        if isinstance(os_label, str) and os_label.strip() and getattr(parser_config, "show_disk_space_by_os", False):
            return "show-disk-space-by-os"
        for flag in ("get_disk_space_ranges", "over_under_tb", "breakdown_by_terabyte"):
            if getattr(parser_config, flag, False):
                return flag.replace("_", "-")
        return "show-disk-space-by-os"
    return "graph"


def _visualizer_config(args: tuple[object, ...]) -> config.Config | None:
    if args and isinstance(args[0], Visualizer):
        return args[0].config
    return None


def _graph_output_dir(args: tuple[object, ...]) -> Path | None:
    cfg = _visualizer_config(args)
    output_dir = getattr(cfg, "graph_output_dir", None) if cfg is not None else None
    return Path(output_dir) if output_dir else None


def _graph_filename(
    visualize_method: Callable[..., object],
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> str:
    """Build a PNG filename from the visualize method and optional OS label."""
    report = _report_name(visualize_method, _visualizer_config(args), kwargs)
    os_label = kwargs.get("os_filter") or kwargs.get("os_name")
    if isinstance(os_label, str) and os_label.strip():
        return f"{report}-{_slug(os_label)}.png"
    return f"{report}.png"


def _unique_graph_path(directory: Path, filename: str) -> Path:
    """Return a path in *directory* for *filename*, appending a numeric suffix to avoid collisions."""
    path = directory / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10001):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find a unique filename for {filename} in {directory} after 10000 attempts")


class Visualizer:
    def __init__(self: t.Self, cfg: config.Config | None = None) -> None:
        self.config = cfg
        output_dir = getattr(cfg, "graph_output_dir", None) if cfg is not None else None
        if output_dir:
            # NOTE: matplotlib.use() is process-global and irreversible. This is
            # safe because a single Visualizer is created per CLI invocation, but
            # callers that mix interactive and file-output Visualizers in the same
            # process should be aware of this constraint.
            matplotlib.use("Agg", force=True)
            Path(output_dir).mkdir(parents=True, exist_ok=True)

    @plotter
    def visualize_disk_space_horizontal(
        self: t.Self,
        dataFrame: pd.DataFrame,
        os_filter: str | None = None,
    ) -> None:
        """Create horizontal bar chart for disk space.

        Args:
            dataFrame (pd.DataFrame): dataframe with Disk Space Counts
            os_filter (str | None, optional): OS name for plot title and filename. Defaults to None.
        """
        # Create a subplot for plotting
        fig, ax = plt.subplots()

        df = dataFrame.copy()
        if len(df.axes) == 2:
            df = df.sum(axis=1)

        # Plot the sorted counts as a horizontal bar chart

        for range, count in df.items():
            ax.barh(f"{range}", count)

        # Set titles and labels for the plot
        plt.ylabel("Disk Space Range")
        plt.xlabel("Number of VMs")
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())

        plt.title(f'Hard Drive Space Breakdown for Organization{f" for {os_filter}" if os_filter else ""}')

    @plotter
    def visualize_disk_space_vertical(
        self: t.Self,
        range_counts_by_environment: pd.DataFrame,
        os_filter: str | None = None,
    ) -> None:
        """Create vertical bar chart for disk space.

        Args:
            dataFrame (pd.DataFrame): dataframe with Disk Space Counts
            os_filter (str | None, optional): Name of filter applied to dataFrame for use in plot title. Defaults to None.
        """
        range_counts_by_environment.plot(kind="bar", stacked=False, figsize=(12, 8), rot=45)

        plt.xlabel("Disk Space Range")
        plt.ylabel("Number of VMs")
        plt.title(f'VM Disk Size Ranges Sorted by Environment {f"for {os_filter}" if os_filter else ""}')

    @plotter
    def visualize_os_distribution(
        self: t.Self,
        counts: pd.Series,
        min_count: int = 500,
    ) -> None:
        """Create horizontal bar chart of OS Counts.

        Args:
            counts (pd.Series): series of counts per os
            min_count (int, optional): minimum count of oses graphed for title. Defaults to 500.
        """
        # this may not be needed anymore, it might be simplifiable to counts.index
        os_names: list[str] = [idx[1] for idx in counts.index] if counts.index.nlevels == 2 else counts.index
        # Plot the counts as a horizontal bar chart with specified and random colors
        counts.plot(kind="barh", rot=45, color=_get_colors(os_names))

        # Set titles and labels for the plot
        plt.title(f"OS Counts by Environment Type (>= {min_count})")
        plt.xlabel("Count")
        plt.ylabel("Operating Systems")

    @plotter
    def visualize_granular_os_distribution(
        self: t.Self,
        counts: pd.Series | pd.DataFrame,
        min_count: int | None = None,
    ) -> None:
        """Create a horizontal bar chart of combined OS Name + Version counts.

        Args:
            counts: Series of totals, or DataFrame split by environment.
            min_count: Optional threshold shown in the title.
        """
        title = "All In-Scope VMs - OS Distribution (Bar Chart)"
        if min_count is not None and min_count > 0:
            title = f"{title} (>= {min_count:,})"

        if isinstance(counts, pd.DataFrame):
            self._plot_granular_os_by_environment(counts, title)
            return
        self._plot_granular_os_series(counts, title)

    def _plot_granular_os_series(self: t.Self, counts: pd.Series, title: str) -> None:
        """Render a single-color horizontal bar chart from a counts Series."""
        labels = [str(label) for label in counts.index]
        values = [int(value) for value in counts.to_list()]
        figure_height = max(4, len(labels) * 0.45)
        figure, axes = plt.subplots(figsize=(10, figure_height))
        y_positions = range(len(labels))
        axes.barh(list(y_positions), values, color=_get_colors(labels))
        axes.set_yticks(list(y_positions))
        axes.set_yticklabels(labels)
        axes.invert_yaxis()
        _annotate_granular_os_totals(axes, values)
        axes.set_xlabel("Number of VMs")
        axes.set_ylabel("Operating Systems")
        axes.set_title(title)
        figure.tight_layout()

    def _plot_granular_os_by_environment(self: t.Self, counts: pd.DataFrame, title: str) -> None:
        """Render a stacked horizontal bar chart with environment columns."""
        environment_order = [name for name in ("non-prod", "prod") if name in counts.columns]
        if not environment_order:
            environment_order = list(counts.columns)
        plot_data = counts[environment_order].copy()
        row_totals = plot_data.sum(axis=1).sort_values(ascending=False)
        plot_data = plot_data.loc[row_totals.index]
        figure_height = max(4, len(plot_data) * 0.45)
        environment_colors = {"non-prod": "tab:orange", "prod": "tab:blue"}
        color_list = [environment_colors.get(name, "tab:gray") for name in environment_order]
        axes = plot_data.plot(
            kind="barh",
            stacked=True,
            figsize=(10, figure_height),
            color=color_list,
        )
        axes.invert_yaxis()
        totals: list[int] = [int(value) for value in row_totals.to_list()]
        _annotate_granular_os_totals(axes, totals)
        axes.set_xlabel("Number of VMs")
        axes.set_ylabel("Operating Systems")
        axes.set_title(title)
        plt.tight_layout()

    @plotter
    def visualize_unsupported_os_distribution(
        self: t.Self,
        counts: pd.Series,
    ) -> None:
        """Create pie chart of unsupported os counts.

        Args:
            counts (pd.Series): series of counts per os
        """
        random_colors = colormaps["rainbow"](np.linspace(0, 1, len(counts)))
        plt.pie(
            counts,
            labels=counts.index,
            colors=random_colors,
            autopct="%1.1f%%",
        )
        plt.title("Unsupported Operating System Distribution")

    @plotter
    def visualize_supported_os_distribution(
        self: t.Self,
        counts: pd.Series,
        environment_filter: str | None = None,
    ) -> None:
        """Create horizontal bar chart of supported os counts.

        Args:
            counts (pd.Series): series of counts per os
            environment_filter (str | None, optional): environment filter for title. Defaults to None.
        """
        colors = [const.SUPPORTED_OS_COLORS[os] for os in counts.index]

        if not environment_filter or environment_filter != "both":
            counts.plot(kind="barh", rot=45, color=colors)
        else:
            counts.plot(kind="barh", rot=45)

        if environment_filter not in ["prod", "non-prod"]:
            plt.title("Supported Operating Systems For All Environments")
        else:
            plt.title(f"Supported Operating Systems for {environment_filter.title()}")

        plt.ylabel("Operating Systems")
        plt.xlabel("Count")
        plt.xscale("log")
        plt.gca().xaxis.set_major_formatter(ticker.ScalarFormatter())

        if environment_filter != "both":
            plt.xticks(
                [
                    counts.iloc[0] - (counts.iloc[0] % 100),
                    counts.iloc[len(counts) // 2] - (counts.iloc[len(counts) // 2] % 100),
                    counts.iloc[-1],
                ]
            )

    @plotter
    def visualize_os_version_distribution(
        self: t.Self,
        dataFrame: pd.DataFrame,
        os_name: str,
    ) -> None:
        """Create horizontal bar chart for os version counts.

        Args:
            dataFrame (pd.DataFrame): dataframe of os version counts
            os_name (str): name of os for title
        """
        ax = dataFrame.plot(kind="barh", rot=45)
        plt.title(f"Distribution of {os_name}")
        plt.ylabel("OS Version")
        plt.xlabel("Count")

        plt.xticks(rotation=0)
        ax.set_yticklabels(dataFrame["OS Version"])


def _annotate_granular_os_totals(axes: plt.Axes, totals: list[int]) -> None:
    """Write count and percent labels to the right of each horizontal bar."""
    grand_total = sum(totals)
    largest_total = max(totals) if totals else 0
    padding = largest_total * 0.01 if largest_total else 0
    for index, total in enumerate(totals):
        percent = (total / grand_total * 100) if grand_total else 0.0
        axes.text(total + padding, index, f"{total:,} VMs ({percent:.1f}%)", va="center")
    if largest_total:
        axes.set_xlim(right=largest_total * 1.25)


def _get_colors(os_names: list[str]) -> list[ColorType]:
    """Generate Colors for OS names of mixed support status.

    Uses np.linspace to generate equally spaced colors, then removes the colors closest
    to the predefined supported os colors.  returns a list with predifined and generated colors ordered by os_names arg

    Args:
        os_names (list[str]): list of os names

    Returns:
        list[ColorType]: matplotlib colors for each os.
    """
    supported_os_names = list(set(os_names).intersection(const.SUPPORTED_OSES))
    supported_os_colors: list[ColorType] = [mcolors.to_rgba(const.SUPPORTED_OS_COLORS[os]) for os in supported_os_names]
    raw_colors: list[ColorType] = colormaps["rainbow"](
        np.linspace(0, 1, len(os_names)),
    ).tolist()
    color_diff: list[float] = [4.0 for _ in raw_colors]

    for idx, rawcolor in enumerate(raw_colors):
        diff: float = 4.0  # Max possible value
        for usedcolor in supported_os_colors:
            new_diff = _color_diff(usedcolor, rawcolor)
            diff = new_diff if new_diff < diff else diff
        color_diff[idx] = diff

    for _ in range(len(supported_os_colors)):
        idx = color_diff.index(min(color_diff))
        del raw_colors[idx]
        del color_diff[idx]

    chosen_colors: list[ColorType] = []
    for os in os_names:
        if os in supported_os_names:
            chosen_colors.append(mcolors.to_rgba(const.SUPPORTED_OS_COLORS[os]))
        else:
            chosen_colors.append(raw_colors.pop())
    return chosen_colors


def _color_diff(color_a: ColorType, color_b: ColorType) -> float:
    """Calculate absolute value of the distance between two colors.

    Args:
        a (ColorType): color to calculate difference
        b (ColorType): color to calculate difference

    Returns:
        float: absolute value of the distance between a and b in rgba color space
    """
    color_tuples = (mcolors.to_rgba(color_a), mcolors.to_rgba(color_b))
    color_values: Iterable[tuple[float, float]] = zip(*color_tuples)
    return math.fsum([abs(a - b) for a, b in color_values])
