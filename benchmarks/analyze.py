"""
Analysis of the benchmark results (SPEC 11.9): reads every CSV in benchmarks/results/ and writes its tables and
figures to benchmarks/report/. Exits with code 1 if a cross-run validity check of SPEC 11.7 fails.

Usage: python benchmarks/analyze.py [--results DIR] [--report DIR]
"""

import argparse
import math
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BENCHMARKS_DIR = Path(__file__).resolve().parent
SHA_FILE = "json_index_sha256.csv"
RERUN_FILE = "rerun_configurations.txt"
KEY = ["language", "experiment", "structure", "n_books", "metric", "unit"]
CONFIGURATION = ["language", "experiment", "structure", "n_books"]
TIME_UNITS = {"ms"}
THROUGHPUT_UNITS = {"books_per_s", "rows_per_s"}
SCALABLE_UNITS = TIME_UNITS | THROUGHPUT_UNITS | {"bytes", "files", "dirs"}
CV_LIMIT = 0.10
REFERENCE_LANGUAGE = "python"
BUILD_PARTS = ["lake_read_time", "metadata_write_time", "index_write_time"]
QUERY_PERCENTILES = ["query_p50", "query_p95", "query_p99"]
QUERY_TERM_MEANS = ["query_mean_t1", "query_mean_t2", "query_mean_t3"]
EQUAL_COUNTS = ["index_terms", "index_postings", "query_results_total"]
PERCENT = 100
FIGURE_DPI = 120


def nearest_rank(values: Sequence[float], percentile: int) -> float:
    """Sample at 1-based position (p x n + 99) div 100 of the ascending samples (SPEC 11.3 rule 5)."""
    ascending = sorted(values)
    return ascending[(percentile * len(ascending) + PERCENT - 1) // PERCENT - 1]


def coefficient_of_variation(values: Sequence[float]) -> float:
    """Sample standard deviation divided by the mean; 0 with fewer than two samples or a zero mean."""
    mean = statistics.fmean(values)
    if len(values) < 2 or mean == 0:
        return 0.0
    return statistics.stdev(values) / mean


def load_results(results_dir: Path) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in sorted(results_dir.glob("*.csv")) if path.name != SHA_FILE]
    if not frames:
        raise SystemExit(f"No results in {results_dir}")
    return pd.concat(frames, ignore_index=True)


def aggregate(results: pd.DataFrame) -> pd.DataFrame:
    """Median and interquartile range over the counted rounds (run >= 1), and the flag of SPEC 11.9 step 1."""
    counted = results[results["run"] >= 1]
    rows = []
    for key, group in counted.groupby(KEY, sort=True):
        values = group["value"].tolist()
        cv = coefficient_of_variation(values)
        is_timed = key[-1] in TIME_UNITS | THROUGHPUT_UNITS
        rows.append(
            {
                **dict(zip(KEY, key, strict=True)),
                "runs": len(values),
                "median": statistics.median(values),
                "p25": nearest_rank(values, 25),
                "p75": nearest_rank(values, 75),
                "cv": cv,
                "flagged": is_timed and cv > CV_LIMIT,
            }
        )
    return pd.DataFrame(rows)


def write_rerun_configurations(aggregated: pd.DataFrame, report_dir: Path) -> int:
    """Configurations with a flagged metric, in the format run_all.sh reads for the 5 extra rounds."""
    flagged = aggregated[aggregated["flagged"]][CONFIGURATION].drop_duplicates()
    lines = [" ".join(str(value) for value in row) for row in flagged.itertuples(index=False)]
    (report_dir / RERUN_FILE).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return len(lines)


def speedup(reference: float, candidate: float, unit: str) -> float:
    """Ratio of medians against Python, above 1 when the candidate is better (SPEC 11.9 step 2)."""
    if unit in THROUGHPUT_UNITS:
        return candidate / reference if reference else math.nan
    return reference / candidate if candidate else math.nan


def summary_table(experiment_rows: pd.DataFrame) -> list[str]:
    """Markdown rows: median [p25-p75] per language and structure, and the speedup relative to Python."""
    languages = sorted(experiment_rows["language"].unique())
    lines = [
        "| metric | unit | structure | "
        + " | ".join(languages)
        + " | "
        + " | ".join(f"x {lang}" for lang in languages)
        + " |",
        "|" + "---|" * (3 + 2 * len(languages)),
    ]
    for (metric, unit, structure), group in experiment_rows.groupby(["metric", "unit", "structure"], sort=True):
        by_language = group.set_index("language")
        cells = [_median_with_range(by_language, lang) if lang in by_language.index else "-" for lang in languages]
        speedups = [
            f"{speedup(by_language.at[REFERENCE_LANGUAGE, 'median'], by_language.at[lang, 'median'], unit):.2f}"
            if lang in by_language.index and REFERENCE_LANGUAGE in by_language.index
            else "-"
            for lang in languages
        ]
        lines.append(f"| {metric} | {unit} | {structure} | " + " | ".join(cells + speedups) + " |")
    return lines


def _median_with_range(by_language: pd.DataFrame, language: str) -> str:
    row = by_language.loc[language]
    return f"{row['median']:.6g} [{row['p25']:.6g}-{row['p75']:.6g}]"


def write_summaries(aggregated: pd.DataFrame, report_dir: Path) -> None:
    """One table per experiment at its largest N (SPEC 11.9 step 2)."""
    for experiment, rows in aggregated.groupby("experiment", sort=True):
        largest = rows["n_books"].max()
        lines = [f"# {experiment}, n_books = {largest}", "", *summary_table(rows[rows["n_books"] == largest]), ""]
        (report_dir / f"summary_{experiment}.md").write_text("\n".join(lines), encoding="utf-8")


def least_squares_slope(sizes: Sequence[float], values: Sequence[float]) -> float:
    """Slope of the least-squares line through the log10-log10 points (SPEC 11.9 step 3)."""
    points = [
        (math.log10(size), math.log10(value))
        for size, value in zip(sizes, values, strict=True)
        if size > 0 and value > 0
    ]
    if len(points) < 2:
        return math.nan
    mean_x = statistics.fmean(x for x, _ in points)
    mean_y = statistics.fmean(y for _, y in points)
    spread = sum((x - mean_x) ** 2 for x, _ in points)
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / spread if spread else math.nan


def plot_scalability(metric_rows: pd.DataFrame, title: str, path: Path) -> list[dict[str, object]]:
    """One panel per structure and one line per language on log-log axes; returns the slopes."""
    structures = sorted(metric_rows["structure"].unique())
    figure, axes = plt.subplots(1, len(structures), figsize=(5 * len(structures), 4), squeeze=False)
    slopes = []
    for axis, structure in zip(axes[0], structures, strict=True):
        for language, line in metric_rows[metric_rows["structure"] == structure].groupby("language", sort=True):
            line = line.sort_values("n_books")
            slope = least_squares_slope(line["n_books"].tolist(), line["median"].tolist())
            axis.plot(line["n_books"], line["median"], marker="o", label=f"{language} (slope {slope:.2f})")
            slopes.append({"structure": structure, "language": language, "slope": slope})
        axis.set_xscale("log")
        axis.set_yscale("log")
        axis.set_title(structure)
        axis.set_xlabel("n_books")
        axis.legend()
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(path, dpi=FIGURE_DPI)
    plt.close(figure)
    return slopes


def write_scalability(aggregated: pd.DataFrame, report_dir: Path) -> None:
    """Every metric of an experiment with several sizes, against N (SPEC 11.9 step 3)."""
    slopes = []
    scalable = aggregated[aggregated["unit"].isin(SCALABLE_UNITS)]
    for (experiment, metric, unit), rows in scalable.groupby(["experiment", "metric", "unit"], sort=True):
        if rows["n_books"].nunique() < 2:
            continue
        path = report_dir / f"scalability_{experiment}_{metric}.png"
        for slope in plot_scalability(rows, f"{experiment}: {metric} ({unit})", path):
            slopes.append({"experiment": experiment, "metric": metric, **slope})
    pd.DataFrame(slopes).to_csv(report_dir / "scalability_slopes.csv", index=False)


def medians_at_largest(aggregated: pd.DataFrame, experiment: str, metrics: list[str]) -> pd.DataFrame:
    """Medians of the metrics at the largest N, one row per language and structure."""
    rows = aggregated[(aggregated["experiment"] == experiment) & (aggregated["metric"].isin(metrics))]
    if rows.empty:
        return pd.DataFrame()
    rows = rows[rows["n_books"] == rows["n_books"].max()]
    return rows.pivot_table(index=["language", "structure"], columns="metric", values="median")


def write_build_breakdown(aggregated: pd.DataFrame, report_dir: Path) -> None:
    """Stacked bars of the build_time parts; the rest is processing (SPEC 11.9 step 4)."""
    parts = medians_at_largest(aggregated, "index", ["build_time", *BUILD_PARTS])
    if parts.empty:
        return
    parts["processing"] = parts["build_time"] - parts[BUILD_PARTS].sum(axis=1)
    stacked = parts[[*BUILD_PARTS, "processing"]]
    stacked.to_csv(report_dir / "build_breakdown.csv")
    axis = stacked.plot(kind="bar", stacked=True, figsize=(10, 5), ylabel="ms", title="build_time breakdown")
    axis.figure.tight_layout()
    axis.figure.savefig(report_dir / "build_breakdown.png", dpi=FIGURE_DPI)
    plt.close(axis.figure)


def write_query_latency(aggregated: pd.DataFrame, report_dir: Path) -> None:
    """Latency percentiles with interquartile error bars, and the mean by number of terms (SPEC 11.9 step 5)."""
    rows = aggregated[(aggregated["experiment"] == "index") & (aggregated["metric"].isin(QUERY_PERCENTILES))]
    if rows.empty:
        return
    rows = rows[rows["n_books"] == rows["n_books"].max()]
    medians = rows.pivot_table(index=["language", "structure"], columns="metric", values="median")
    lower = medians - rows.pivot_table(index=["language", "structure"], columns="metric", values="p25")
    upper = rows.pivot_table(index=["language", "structure"], columns="metric", values="p75") - medians
    errors = [[lower[metric].tolist(), upper[metric].tolist()] for metric in medians.columns]
    axis = medians.plot(kind="bar", yerr=errors, figsize=(10, 5), ylabel="ms", title="query latency")
    axis.figure.tight_layout()
    axis.figure.savefig(report_dir / "query_latency.png", dpi=FIGURE_DPI)
    plt.close(axis.figure)
    by_terms = medians_at_largest(aggregated, "index", QUERY_TERM_MEANS)
    axis = by_terms.plot(kind="bar", figsize=(10, 5), ylabel="ms", title="query mean by number of terms")
    axis.figure.tight_layout()
    axis.figure.savefig(report_dir / "query_terms.png", dpi=FIGURE_DPI)
    plt.close(axis.figure)


def write_memory(aggregated: pd.DataFrame, report_dir: Path) -> None:
    """peak_rss minus the baseline of the same language (SPEC 11.9 step 6)."""
    peaks = aggregated[aggregated["metric"] == "peak_rss"]
    baseline = peaks[peaks["experiment"] == "baseline"].set_index("language")["median"]
    measured = peaks[peaks["experiment"] != "baseline"].copy()
    if measured.empty or baseline.empty:
        return
    measured["over_baseline_bytes"] = measured["median"] - measured["language"].map(baseline)
    columns = ["language", "experiment", "structure", "n_books", "median", "over_baseline_bytes"]
    measured[columns].to_csv(report_dir / "memory.csv", index=False)
    largest = measured[measured["n_books"] == measured.groupby("experiment")["n_books"].transform("max")]
    table = largest.pivot_table(index=["experiment", "structure"], columns="language", values="over_baseline_bytes")
    axis = table.plot(kind="bar", figsize=(10, 5), ylabel="bytes", title="peak_rss over baseline, largest N")
    axis.figure.tight_layout()
    axis.figure.savefig(report_dir / "memory.png", dpi=FIGURE_DPI)
    plt.close(axis.figure)


def validity_problems(results: pd.DataFrame, results_dir: Path) -> list[str]:
    """The cross-run checks of SPEC 11.7 and recovery_correct_* (SPEC 11.9 step 7)."""
    problems = []
    counts = results[(results["experiment"] == "index") & (results["metric"].isin(EQUAL_COUNTS))]
    for (n_books, metric), group in counts.groupby(["n_books", "metric"]):
        if group["value"].nunique() > 1:
            problems.append(f"{metric} differs for n_books={n_books}: {sorted(float(value) for value in group['value'].unique())}")
    recovery = results[results["metric"].str.startswith("recovery_correct_")]
    for row in recovery[recovery["value"] != 1].itertuples(index=False):
        problems.append(f"{row.metric}=0 for {row.language} {row.structure} n_books={row.n_books} run={row.run}")
    sha_path = results_dir / SHA_FILE
    if sha_path.is_file():
        for n_books, group in pd.read_csv(sha_path).groupby("n_books"):
            if group["sha256"].nunique() > 1:
                problems.append(f"inverted_index.json differs across languages or runs for n_books={n_books}")
    return problems


def write_validity(problems: list[str], report_dir: Path) -> None:
    lines = ["# Validity (SPEC 11.7)", ""]
    lines += [f"- {problem}" for problem in problems] if problems else ["All cross-run checks passed."]
    (report_dir / "validity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=BENCHMARKS_DIR / "results")
    parser.add_argument("--report", type=Path, default=BENCHMARKS_DIR / "report")
    arguments = parser.parse_args()
    plt.switch_backend("Agg")
    arguments.report.mkdir(parents=True, exist_ok=True)
    results = load_results(arguments.results)
    aggregated = aggregate(results)
    aggregated.to_csv(arguments.report / "aggregated.csv", index=False)
    flagged = write_rerun_configurations(aggregated, arguments.report)
    write_summaries(aggregated, arguments.report)
    write_scalability(aggregated, arguments.report)
    write_build_breakdown(aggregated, arguments.report)
    write_query_latency(aggregated, arguments.report)
    write_memory(aggregated, arguments.report)
    problems = validity_problems(results, arguments.results)
    write_validity(problems, arguments.report)
    print(f"Report written to {arguments.report}: {flagged} configurations flagged, {len(problems)} validity problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
