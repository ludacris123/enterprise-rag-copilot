import io
import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, mean_absolute_error, r2_score
from .config import get_settings


def train_model(payload, job_id):
    df = pd.read_csv(io.StringIO(payload["csv"]))
    target = payload["target"]
    if target not in df.columns or not 30 <= len(df) <= 10000 or len(df.columns) > 60:
        raise ValueError("CSV must have 30–10,000 rows, at most 60 columns, and the selected target")
    if df.columns.duplicated().any():
        raise ValueError("Column names must be unique")
    df = df.dropna(subset=[target])
    x, y = df.drop(columns=[target]), df[target]
    if x.empty or any(df[c].nunique() > 500 for c in x.select_dtypes(exclude="number").columns):
        raise ValueError("Remove identifier/high-cardinality columns before training")
    classification = payload["task"] == "classification"
    if classification and (y.nunique() < 2 or y.nunique() > 20 or y.value_counts().min() < 3):
        raise ValueError("Classification requires 2–20 classes with at least 3 rows per class")
    if not classification:
        y = pd.to_numeric(y, errors="raise")
    # Split first: preprocessing is fitted only on the training partition.
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=42, stratify=y if classification else None)
    numeric = list(x.select_dtypes(include="number").columns)
    categorical = [c for c in x.columns if c not in numeric]
    pre = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median", keep_empty_features=True)), ("scale", StandardScaler())]), numeric),
        ("category", Pipeline([("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
                               ("encode", OneHotEncoder(handle_unknown="ignore"))]), categorical)])
    estimator = (RandomForestClassifier(n_estimators=80, max_depth=12, random_state=42, n_jobs=1) if classification else
                 RandomForestRegressor(n_estimators=80, max_depth=12, random_state=42, n_jobs=1)) if payload["algorithm"] == "random_forest" else (
                 LogisticRegression(max_iter=1000) if classification else Ridge())
    pipeline = Pipeline([("preprocess", pre), ("model", estimator)])
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    if classification:
        labels = pipeline.classes_
        metrics = {"accuracy": float(accuracy_score(y_test, predictions)), "weighted_f1": float(f1_score(y_test, predictions, average="weighted")),
                   "confusion_matrix": confusion_matrix(y_test, predictions, labels=labels).tolist(), "labels": [str(v) for v in labels]}
    else:
        metrics = {"mae": float(mean_absolute_error(y_test, predictions)), "r2": float(r2_score(y_test, predictions))}
    directory = Path(get_settings().artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{job_id}.joblib"
    temporary = directory / f"{job_id}.tmp"
    joblib.dump({"pipeline": pipeline, "columns": list(x.columns)}, temporary)
    os.replace(temporary, destination)
    return {"metrics": metrics, "target": target, "task": payload["task"], "algorithm": payload["algorithm"],
            "training_rows": len(x_train), "test_rows": len(x_test), "features": list(x.columns),
            "split": "Stratified 75/25" if classification else "Random 75/25", "seed": 42}


def predict(job_id, rows):
    # Only server-generated artifacts with an authorized DB job ID can reach this loader.
    saved = joblib.load(Path(get_settings().artifact_dir) / f"{job_id}.joblib")
    frame = pd.DataFrame(rows)
    if set(frame.columns) != set(saved["columns"]):
        raise ValueError("Prediction columns must match the training features")
    output = saved["pipeline"].predict(frame[saved["columns"]])
    return {"predictions": [v.item() if isinstance(v, np.generic) else v for v in output]}
