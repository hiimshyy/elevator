"""CLI script to export ML models to ONNX format."""
import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType


FEATURE_NAMES = [
    "accel_rms_mean",
    "accel_rms_std",
    "accel_delta",
    "accel_roc",
    "velocity_rms_z",
    "peak_to_rms_ratio",
    "motor_temp_delta",
    "humidity_trend",
    "load_pct",
    "load_variance",
    "multivariate_score",
]


def generate_sample_data(n_samples=17280, seed=42):
    """Generate synthetic training data for Isolation Forest.

    Args:
        n_samples: Number of samples to generate.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with feature columns.
    """
    np.random.seed(seed)
    import math

    data = []
    for i in range(n_samples):
        hour = (i * 5) / 3600 % 24
        time_factor = 1.0 + 0.1 * math.sin(2 * math.pi * hour / 24)

        row = [
            (30.0 * time_factor + np.random.uniform(-5, 5)),  # accel_rms_mean
            np.random.uniform(2, 15) * time_factor,  # accel_rms_std
            np.random.uniform(-10, 10),  # accel_delta
            np.random.uniform(-5, 5),  # accel_roc
            np.random.uniform(-1.5, 1.5),  # velocity_rms_z
            np.random.uniform(1.2, 2.5),  # peak_to_rms_ratio
            np.random.uniform(5, 25),  # motor_temp_delta
            np.random.uniform(-0.5, 0.5),  # humidity_trend
            np.random.uniform(0.05, 0.85),  # load_pct
            np.random.uniform(5, 50),  # load_variance
            np.random.uniform(0.05, 0.4),  # multivariate_score
        ]
        data.append(row)

    return pd.DataFrame(data, columns=FEATURE_NAMES)


def train_isolation_forest(data, contamination=0.05, n_estimators=100):
    """Train an Isolation Forest model.

    Args:
        data: Training data DataFrame.
        contamination: Contamination parameter for IsolationForest.
        n_estimators: Number of trees in the forest.

    Returns:
        Trained IsolationForest model.
    """
    model = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=42,
    )
    model.fit(data.values)
    return model


def export_to_onnx(model, output_path, n_features=11, opset=15):
    """Export a trained model to ONNX format.

    Args:
        model: Trained sklearn model.
        output_path: Path to save the ONNX model.
        n_features: Number of input features.
        opset: ONNX opset version.
    """
    initial_type = [("float_input", FloatTensorType([None, n_features]))]
    # Use opset dict to specify ai.onnx.ml domain version
    onnx_model = convert_sklearn(
        model,
        initial_types=initial_type,
        target_opset={"": opset, "ai.onnx.ml": 3},
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"Model exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Export ML models to ONNX format")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        choices=["isolation_forest"],
        help="Model type to export",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/vibration_anomaly_v1.onnx",
        help="Output path for ONNX file",
    )
    parser.add_argument(
        "--contamination",
        type=float,
        default=0.05,
        help="Contamination parameter for Isolation Forest (default: 0.05)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to training CSV (optional, generates sample data if not provided)",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees in Isolation Forest (default: 100)",
    )

    args = parser.parse_args()

    # Load or generate training data
    if args.data and os.path.exists(args.data):
        print(f"Loading training data from: {args.data}")
        df = pd.read_csv(args.data)
    else:
        print("Generating sample training data...")
        df = generate_sample_data()
        print(f"Generated {len(df)} samples")

    print(f"Feature names: {list(df.columns)}")
    print(f"Data shape: {df.shape}")

    # Train model
    print(f"\nTraining Isolation Forest (contamination={args.contamination})...")
    model = train_isolation_forest(
        df,
        contamination=args.contamination,
        n_estimators=args.n_estimators,
    )
    print("Training complete")

    # Export to ONNX
    print(f"\nExporting to ONNX: {args.output}")
    export_to_onnx(model, args.output, n_features=len(df.columns))

    # Verify exported model
    import onnx

    onnx_model = onnx.load(args.output)
    print(f"\nVerified ONNX model:")
    print(f"  IR version: {onnx_model.ir_version}")
    print(f"  Inputs: {[inp.name for inp in onnx_model.graph.input]}")
    print(f"  Outputs: {[out.name for out in onnx_model.graph.output]}")


if __name__ == "__main__":
    main()
