"""
Demand forecasting model using:
  - PyTorch neural network (3-layer MLP)
  - ANOVA F-test for feature significance ranking
  - Features: distance, airport size, continent, elevation, is_international,
              is_transatlantic, is_transpacific, hour_of_day, season

ANOVA tells us WHICH features significantly affect demand (p < 0.05).
PyTorch learns the non-linear interactions between them.
"""
import os, sys, json
import numpy as np
import pandas as pd
import psycopg2
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from scipy import stats
import joblib

DB  = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/airline_opt")
DIR = os.path.dirname(__file__)
MODEL_PATH   = os.path.join(DIR, "demand_model.pt")
SCALER_PATH  = os.path.join(DIR, "demand_scaler.joblib")
ANOVA_PATH   = os.path.join(DIR, "anova_results.json")

CONTINENT_MAP = {"EU":0,"NA":1,"AS":2,"OC":3,"SA":4,"AF":5,"AN":6}
SIZE_MAP      = {"large_airport":2,"medium_airport":1,"small_airport":0,
                 "heliport":0,"seaplane_base":0}


# ── PyTorch Model ─────────────────────────────────────────────────────────────
class DemandNet(nn.Module if nn is not None else object):
    def __init__(self, n_features: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        return self.net(x).squeeze(1)


# ── Feature engineering ───────────────────────────────────────────────────────
def build_features(df: pd.DataFrame) -> np.ndarray:
    feats = pd.DataFrame()
    feats["log_distance"]      = np.log1p(df["distance_km"])
    feats["distance_sq"]       = (df["distance_km"] / 10000) ** 2
    feats["size_origin"]       = df["type_origin"].map(SIZE_MAP).fillna(0)
    feats["size_dest"]         = df["type_dest"].map(SIZE_MAP).fillna(0)
    feats["continent_origin"]  = df["continent_origin"].map(CONTINENT_MAP).fillna(3)
    feats["continent_dest"]    = df["continent_dest"].map(CONTINENT_MAP).fillna(3)
    feats["is_international"]  = (df["country_origin"] != df["country_dest"]).astype(float)
    feats["is_transatlantic"]  = (
        ((df["lon_origin"] < -20) & (df["lon_dest"] > -20)) |
        ((df["lon_origin"] > -20) & (df["lon_dest"] < -20))
    ).astype(float)
    feats["is_transpacific"]   = (
        ((df["lon_origin"] > 100) & (df["lon_dest"] < -100)) |
        ((df["lon_origin"] < -100) & (df["lon_dest"] > 100))
    ).astype(float)
    feats["elevation_origin"]  = df.get("elevation_ft_origin", pd.Series(0, index=df.index)).fillna(0) / 10000
    feats["lat_abs_origin"]    = df["lat_origin"].abs() / 90
    feats["same_continent"]    = (df["continent_origin"] == df["continent_dest"]).astype(float)
    return feats.values.astype(np.float32)


# ── ANOVA feature significance ────────────────────────────────────────────────
def run_anova(df: pd.DataFrame, X: np.ndarray, y: np.ndarray) -> dict:
    """
    One-way ANOVA: for each categorical feature, test if group means of demand differ.
    For continuous features, use Pearson correlation + F-statistic.
    """
    feature_names = [
        "log_distance","distance_sq","size_origin","size_dest",
        "continent_origin","continent_dest","is_international",
        "is_transatlantic","is_transpacific","elevation_origin",
        "lat_abs_origin","same_continent"
    ]
    results = {}
    for i, name in enumerate(feature_names):
        col = X[:, i]
        # Bin continuous features into groups for ANOVA
        try:
            n_bins = min(5, len(np.unique(col)))
            if n_bins < 2:
                results[name] = {"f_stat": 0.0, "p_value": 1.0, "significant": False}
                continue
            bins = pd.qcut(col, q=n_bins, duplicates="drop")
            groups = [y[bins == b] for b in bins.cat.categories if len(y[bins == b]) > 1]
            if len(groups) < 2:
                results[name] = {"f_stat": 0.0, "p_value": 1.0, "significant": False}
                continue
            f_stat, p_value = stats.f_oneway(*groups)
            results[name] = {
                "f_stat":      round(float(f_stat), 4),
                "p_value":     round(float(p_value), 6),
                "significant": bool(p_value < 0.05),
                "eta_squared": round(float(f_stat / (f_stat + len(y))), 6)
            }
        except Exception:
            results[name] = {"f_stat": 0.0, "p_value": 1.0, "significant": False}

    # Sort by F-statistic descending
    results = dict(sorted(results.items(), key=lambda x: -x[1]["f_stat"]))
    print("\n  ANOVA Feature Significance:")
    print(f"  {'Feature':<22} {'F-stat':>10} {'p-value':>12} {'Significant':>12}")
    print("  " + "-" * 58)
    for name, r in results.items():
        sig = "✓" if r["significant"] else "✗"
        print(f"  {name:<22} {r['f_stat']:>10.2f} {r['p_value']:>12.6f} {sig:>12}")
    return results


# ── Load data from DB ─────────────────────────────────────────────────────────
def load_training_data() -> pd.DataFrame:
    conn = psycopg2.connect(DB)
    df = pd.read_sql("""
        SELECT
            r.distance_km,
            r.base_demand,
            r.base_fare_usd,
            a1.type        AS type_origin,
            a2.type        AS type_dest,
            a1.continent   AS continent_origin,
            a2.continent   AS continent_dest,
            a1.country     AS country_origin,
            a2.country     AS country_dest,
            a1.lon         AS lon_origin,
            a2.lon         AS lon_dest,
            a1.lat         AS lat_origin,
            a1.elevation_ft AS elevation_ft_origin
        FROM routes r
        JOIN airports a1 ON a1.iata = r.origin
        JOIN airports a2 ON a2.iata = r.destination
        WHERE r.distance_km IS NOT NULL
          AND r.base_demand IS NOT NULL
          AND r.base_demand > 0
        LIMIT 150000
    """, conn)
    conn.close()
    return df


# ── Train ─────────────────────────────────────────────────────────────────────
def train():
    print("Loading training data from DB...")
    df = load_training_data()
    print(f"  {len(df)} routes loaded")

    X = build_features(df)
    y = np.log1p(df["base_demand"].values.astype(np.float32))  # log-transform target

    # ANOVA
    print("\nRunning ANOVA feature significance tests...")
    anova_results = run_anova(df, X, y)
    with open(ANOVA_PATH, "w") as f:
        json.dump(anova_results, f, indent=2)
    print(f"\n  ANOVA results saved → {ANOVA_PATH}")

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X).astype(np.float32)
    joblib.dump(scaler, SCALER_PATH)

    X_train, X_val, y_train, y_val = train_test_split(X_scaled, y, test_size=0.15, random_state=42)

    train_ds = TensorDataset(torch.tensor(X_train), torch.tensor(y_train))
    val_ds   = TensorDataset(torch.tensor(X_val),   torch.tensor(y_val))
    train_dl = DataLoader(train_ds, batch_size=512, shuffle=True)
    val_dl   = DataLoader(val_ds,   batch_size=512)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = DemandNet(X.shape[1]).to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched  = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=3, factor=0.5)
    loss_fn = nn.HuberLoss()

    print(f"\nTraining DemandNet on {device} — {X.shape[1]} features, {len(X_train)} samples")
    print(f"  {'Epoch':>6} {'Train Loss':>12} {'Val Loss':>12} {'Val MAE':>10}")
    print("  " + "-" * 44)

    best_val = float("inf")
    metrics_log = []

    for epoch in range(1, 51):
        model.train()
        train_loss = 0.0
        for xb, yb in train_dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(train_ds)

        model.eval()
        val_loss, val_mae = 0.0, 0.0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb)
                val_loss += loss_fn(pred, yb).item() * len(xb)
                val_mae  += (torch.expm1(pred) - torch.expm1(yb)).abs().mean().item() * len(xb)
        val_loss /= len(val_ds)
        val_mae  /= len(val_ds)
        sched.step(val_loss)

        metrics_log.append({"epoch": epoch, "train_loss": train_loss,
                             "val_loss": val_loss, "val_mae": val_mae})

        if epoch % 5 == 0 or epoch == 1:
            print(f"  {epoch:>6} {train_loss:>12.4f} {val_loss:>12.4f} {val_mae:>10.1f}")

        if val_loss < best_val:
            best_val = val_loss
            torch.save({"model_state": model.state_dict(),
                        "n_features": X.shape[1],
                        "metrics": metrics_log}, MODEL_PATH)

    # Save metrics to DB
    conn = psycopg2.connect(DB)
    cur  = conn.cursor()
    for m in metrics_log:
        for metric in ["train_loss", "val_loss", "val_mae"]:
            cur.execute("""
                INSERT INTO model_metrics (model_name, metric_name, value, epoch)
                VALUES ('DemandNet', %s, %s, %s)
            """, (metric, m[metric], m["epoch"]))
    conn.commit(); cur.close(); conn.close()

    print(f"\n✓ Model saved → {MODEL_PATH}")
    print(f"  Best val loss: {best_val:.4f}")
    return model, scaler


# ── Inference ─────────────────────────────────────────────────────────────────
def load_model():
    ckpt   = torch.load(MODEL_PATH, map_location="cpu")
    model  = DemandNet(ckpt["n_features"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def predict_demand(model, scaler, route_dict: dict) -> int:
    df   = pd.DataFrame([route_dict])
    X    = build_features(df)
    Xs   = scaler.transform(X).astype(np.float32)
    with torch.no_grad():
        log_pred = model(torch.tensor(Xs)).item()
    return max(1, int(np.expm1(log_pred)))


# ── Fuel economics ────────────────────────────────────────────────────────────
FUEL_BURN_KG_PER_KM  = 12.0
FUEL_PRICE_USD_PER_KG = 0.85
FIXED_COST_PER_FLIGHT = 8_000
SEATS = 180

def fuel_cost(distance_km: float, wind_factor: float = 1.0, detour_km: float = 0.0) -> float:
    return (distance_km + detour_km) * wind_factor * FUEL_BURN_KG_PER_KM * FUEL_PRICE_USD_PER_KG

def route_profit(distance_km, demand, fare, frequency, wind_factor=1.0, detour_km=0.0, seats=180) -> dict:
    fc      = fuel_cost(distance_km, wind_factor, detour_km)
    revenue = min(demand, seats) * fare * frequency
    total   = (fc + FIXED_COST_PER_FLIGHT) * frequency
    return {
        "revenue":         revenue,
        "fuel_cost":       fc * frequency,
        "fixed_cost":      FIXED_COST_PER_FLIGHT * frequency,
        "profit":          revenue - total,
        "wind_saving_usd": (fuel_cost(distance_km) - fc) * frequency,
        "detour_cost_usd": fuel_cost(detour_km, wind_factor) * frequency,
    }


if __name__ == "__main__":
    train()
