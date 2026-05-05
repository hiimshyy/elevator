"""Generate sample vibration feature data for Isolation Forest training."""
import csv
import random
import math


def generate_sample_data(num_samples=17280, output_path="notebooks/data/sample_vibration_features.csv"):
    """Generate synthetic data representing normal elevator operation.

    Args:
        num_samples: Number of samples (17280 = 48h × 3600s/h ÷ 5s interval)
        output_path: Path to output CSV file
    """
    random.seed(42)  # Reproducible

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'accel_rms_mean', 'accel_rms_std', 'accel_delta', 'accel_roc',
            'velocity_rms_z', 'peak_to_rms_ratio', 'motor_temp_delta',
            'humidity_trend', 'load_pct', 'load_variance', 'multivariate_score'
        ])

        for i in range(num_samples):
            # Simulate time-of-day effects (slightly higher vibration during peak hours)
            hour = (i * 5) / 3600 % 24
            time_factor = 1.0 + 0.1 * math.sin(2 * math.pi * hour / 24)

            # Base vibration with realistic noise
            base_vibration = 30.0 * time_factor
            accel_rms_mean = base_vibration + random.uniform(-5, 5)
            accel_rms_std = random.uniform(2, 15) * time_factor
            accel_delta = random.uniform(-10, 10)
            accel_roc = random.uniform(-5, 5)

            # Velocity Z-score (normally distributed around 0)
            velocity_rms_z = random.uniform(-1.5, 1.5)

            # Peak to RMS ratio (typically 1.2-2.5 for normal operation)
            peak_to_rms_ratio = random.uniform(1.2, 2.5)

            # Motor temp delta (motor typically 5-25°C above environment)
            motor_temp_delta = random.uniform(5, 25)

            # Humidity trend (slow changes)
            humidity_trend = random.uniform(-0.5, 0.5)

            # Load percentage (0.05 to 0.85 of capacity)
            load_pct = random.uniform(0.05, 0.85)

            # Load variance (depends on usage pattern)
            load_variance = random.uniform(5, 50)

            # Multivariate score (composite, lower = healthier)
            multivariate_score = random.uniform(0.05, 0.4)

            writer.writerow([
                round(accel_rms_mean, 2),
                round(accel_rms_std, 2),
                round(accel_delta, 2),
                round(accel_roc, 2),
                round(velocity_rms_z, 3),
                round(peak_to_rms_ratio, 2),
                round(motor_temp_delta, 1),
                round(humidity_trend, 3),
                round(load_pct, 3),
                round(load_variance, 1),
                round(multivariate_score, 3),
            ])

    print(f"Generated {num_samples} samples -> {output_path}")


if __name__ == "__main__":
    generate_sample_data()
