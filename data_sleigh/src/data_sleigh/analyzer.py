"""Water level segment analysis for consumption patterns and predictions."""

import logging
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


def analyze_water_level_segments(
    conn: duckdb.DuckDBPyConnection
) -> dict[str, Any] | None:
    """Analyze water level data to detect consumption segments and predict refill time.

    Args:
        conn: DuckDB connection

    Returns:
        Dictionary containing segments, extrema, and current prediction, or None if
        insufficient data for analysis
    """
    try:
        # Query all historical data for analysis
        query = """
        SELECT
            timestamp,
            CAST(payload AS DOUBLE) as distance_mm
        FROM water_level
        WHERE topic = 'xmas/tree/water/raw'
          AND payload IS NOT NULL
        ORDER BY timestamp ASC
        """

        df = conn.execute(query).df()

        if len(df) < 100:  # Need sufficient data for analysis
            return None

        # Basic preprocessing
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.dropna(subset=["timestamp", "distance_mm"])
        df = df.sort_values("timestamp")

        # Outlier removal via rolling-median + MAD
        ROLL_WIN = "5min"
        MAD_MULTIPLIER = 6.0

        ts_indexed = df.set_index("timestamp")
        local_median = (
            ts_indexed["distance_mm"]
            .rolling(ROLL_WIN, center=True, min_periods=1)
            .median()
        )

        df["local_median"] = local_median.values
        df["residual"] = df["distance_mm"] - df["local_median"]

        residuals = df["residual"].dropna()
        mad = np.median(np.abs(residuals - residuals.median()))
        if mad == 0:
            mad = residuals.std(ddof=0)

        threshold = MAD_MULTIPLIER * mad
        df["is_outlier"] = df["residual"].abs() > threshold
        df_clean = df.loc[~df["is_outlier"]].copy()

        if len(df_clean) < 50:
            return None

        # Smoothing for analysis and extrema detection
        SMOOTH_WIN = "10min"
        ts_clean = df_clean.set_index("timestamp")
        df_clean["distance_smooth"] = (
            ts_clean["distance_mm"]
            .rolling(SMOOTH_WIN, center=True, min_periods=1)
            .median()
            .values
        )

        df_clean = df_clean.dropna(subset=["distance_smooth"]).reset_index(drop=True)
        df_clean["index"] = df_clean.index

        # Detect local minima and maxima
        PROMINENCE_MM = 5.0
        MIN_PEAK_DISTANCE_SAMPLES = 20

        series = df_clean["distance_smooth"].to_numpy()

        # Maxima (local peaks)
        max_idx, _ = find_peaks(
            series, prominence=PROMINENCE_MM, distance=MIN_PEAK_DISTANCE_SAMPLES
        )

        # Minima: peaks of inverted series
        min_idx, _ = find_peaks(
            -series, prominence=PROMINENCE_MM, distance=MIN_PEAK_DISTANCE_SAMPLES
        )

        maxima = df_clean.iloc[max_idx][["timestamp", "distance_smooth"]].copy()
        minima = df_clean.iloc[min_idx][["timestamp", "distance_smooth"]].copy()

        # Build segments: rising between a minimum and next maximum
        MIN_SEG_DURATION = pd.Timedelta("3h")
        MIN_SEG_POINTS = 20

        segments = []
        max_idx_sorted = np.sort(max_idx)
        min_idx_sorted = np.sort(min_idx)

        for mn in min_idx_sorted:
            after = max_idx_sorted[max_idx_sorted > mn]
            if len(after) == 0:
                # This is the current segment - handle separately
                continue
            mx = after[0]

            seg = df_clean[
                (df_clean["index"] >= mn) & (df_clean["index"] <= mx)
            ].copy()
            if len(seg) < MIN_SEG_POINTS:
                continue

            duration = seg["timestamp"].iloc[-1] - seg["timestamp"].iloc[0]
            if duration < MIN_SEG_DURATION:
                continue

            segments.append({"min_index": mn, "max_index": mx, "data": seg})

        # Calculate slopes for each completed segment
        segment_list = []
        for i, seg_info in enumerate(segments, start=1):
            seg = seg_info["data"]

            t0 = seg["timestamp"].iloc[0]
            x_hours = (
                (seg["timestamp"] - t0).dt.total_seconds().values.reshape(-1, 1)
                / 3600.0
            )
            y = seg["distance_smooth"].values

            model = LinearRegression().fit(x_hours, y)
            slope = model.coef_[0]  # mm/hour

            # Only include rising segments (consumption)
            if slope > 0:
                segment_list.append({
                    "id": i,
                    "start_time": seg["timestamp"].iloc[0].isoformat(),
                    "end_time": seg["timestamp"].iloc[-1].isoformat(),
                    "start_distance_mm": round(
                        float(seg["distance_smooth"].iloc[0]), 2
                    ),
                    "end_distance_mm": round(
                        float(seg["distance_smooth"].iloc[-1]), 2
                    ),
                    "slope_mm_per_hr": round(float(slope), 3),
                    "duration_hours": round(
                        (
                            seg["timestamp"].iloc[-1] - seg["timestamp"].iloc[0]
                        ).total_seconds()
                        / 3600.0,
                        2,
                    ),
                    "n_points": len(seg),
                    "is_current": False,
                })

        # Handle current segment (from last minimum to now)
        current_prediction = None
        if len(min_idx_sorted) > 0:
            last_min = min_idx_sorted[-1]
            current_seg = df_clean[df_clean["index"] >= last_min].copy()

            if len(current_seg) >= MIN_SEG_POINTS:
                duration = (
                    current_seg["timestamp"].iloc[-1]
                    - current_seg["timestamp"].iloc[0]
                )

                if duration >= pd.Timedelta("1h"):  # At least 1 hour for current segment
                    t0 = current_seg["timestamp"].iloc[0]
                    x_hours = (
                        (current_seg["timestamp"] - t0)
                        .dt.total_seconds()
                        .values.reshape(-1, 1)
                        / 3600.0
                    )
                    y = current_seg["distance_smooth"].values

                    model = LinearRegression().fit(x_hours, y)
                    slope = model.coef_[0]

                    if slope > 0:
                        current_distance = float(
                            current_seg["distance_smooth"].iloc[-1]
                        )
                        remaining_mm = 50.0 - current_distance

                        if remaining_mm > 0:
                            hours_to_50mm = remaining_mm / slope
                            predicted_time = current_seg[
                                "timestamp"
                            ].iloc[-1] + pd.Timedelta(hours=hours_to_50mm)

                            current_prediction = {
                                "current_distance_mm": round(current_distance, 2),
                                "slope_mm_per_hr": round(float(slope), 3),
                                "time_to_50mm_hours": round(hours_to_50mm, 2),
                                "predicted_refill_time": predicted_time.isoformat(),
                            }

                        # Add current segment to segment list
                        segment_list.append({
                            "id": len(segment_list) + 1,
                            "start_time": current_seg["timestamp"]
                            .iloc[0]
                            .isoformat(),
                            "end_time": current_seg["timestamp"].iloc[-1].isoformat(),
                            "start_distance_mm": round(
                                float(current_seg["distance_smooth"].iloc[0]), 2
                            ),
                            "end_distance_mm": round(
                                float(current_seg["distance_smooth"].iloc[-1]), 2
                            ),
                            "slope_mm_per_hr": round(float(slope), 3),
                            "duration_hours": round(
                                (
                                    current_seg["timestamp"].iloc[-1]
                                    - current_seg["timestamp"].iloc[0]
                                ).total_seconds()
                                / 3600.0,
                                2,
                            ),
                            "n_points": len(current_seg),
                            "is_current": True,
                        })

        # Convert extrema to JSON-serializable format
        extrema = {
            "minima": [
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "distance_mm": round(float(row["distance_smooth"]), 2),
                }
                for _, row in minima.iterrows()
            ],
            "maxima": [
                {
                    "timestamp": row["timestamp"].isoformat(),
                    "distance_mm": round(float(row["distance_smooth"]), 2),
                }
                for _, row in maxima.iterrows()
            ],
        }

        return {
            "segments": segment_list,
            "extrema": extrema,
            "current_prediction": current_prediction,
        }

    except Exception as e:
        logger.warning(f"Could not perform segment analysis: {e}")
        return None



