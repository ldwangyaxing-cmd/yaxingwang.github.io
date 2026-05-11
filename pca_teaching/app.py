import os
import io
import base64
import json

import numpy as np
from flask import Flask, render_template, request, jsonify
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.datasets import load_iris, load_wine
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACES_PATH = os.path.join(BASE_DIR, "faces_40.npy")

FACES_DATA = None
def get_faces():
    global FACES_DATA
    if FACES_DATA is None:
        if os.path.exists(FACES_PATH):
            FACES_DATA = np.load(FACES_PATH)
        else:
            from sklearn.datasets import fetch_olivetti_faces
            faces = fetch_olivetti_faces()
            indices = list(range(0, 400, 10))
            FACES_DATA = faces.data[indices].astype(np.float32)
            np.save(FACES_PATH, FACES_DATA)
    return FACES_DATA


def fig_to_base64(fig, dpi=100):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="#1e1e2e", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def np_img_to_base64(arr, size=None):
    arr = np.clip(arr, 0, 1)
    img = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
    if size:
        img = img.resize(size, Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/2d_demo", methods=["POST"])
def api_2d_demo():
    """Generate 2D data, apply PCA, return scatter + eigenvectors."""
    data = request.get_json()
    n_points = min(int(data.get("n_points", 100)), 500)
    spread_x = float(data.get("spread_x", 3.0))
    spread_y = float(data.get("spread_y", 1.0))
    angle_deg = float(data.get("angle", 30))
    seed = int(data.get("seed", 42))

    rng = np.random.RandomState(seed)
    angle = np.radians(angle_deg)
    rot = np.array([[np.cos(angle), -np.sin(angle)],
                    [np.sin(angle),  np.cos(angle)]])

    raw = rng.randn(n_points, 2) * [spread_x, spread_y]
    X = raw @ rot.T

    scaler = StandardScaler()
    X_std = scaler.fit_transform(X)

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_std)

    ev = pca.explained_variance_ratio_

    # Plot original with eigenvectors
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    colors = {"text": "#cdd6f4", "grid": "#45475a", "bg": "#1e1e2e"}
    for ax in axes:
        ax.set_facecolor(colors["bg"])
        ax.tick_params(colors=colors["text"])
        for spine in ax.spines.values():
            spine.set_color(colors["grid"])

    # Panel 1: Original data + principal axes
    ax = axes[0]
    ax.scatter(X_std[:, 0], X_std[:, 1], c="#89b4fa", s=15, alpha=0.7)
    mean = X_std.mean(axis=0)
    for i, (comp, var) in enumerate(zip(pca.components_, pca.explained_variance_)):
        color = "#f38ba8" if i == 0 else "#a6e3a1"
        scale = np.sqrt(var) * 2
        ax.annotate("", xy=mean + comp * scale, xytext=mean,
                     arrowprops=dict(arrowstyle="->", color=color, lw=2.5))
        ax.text(mean[0] + comp[0]*scale*1.15, mean[1] + comp[1]*scale*1.15,
                f"PC{i+1} ({ev[i]*100:.1f}%)", color=color, fontsize=9, fontweight="bold")
    ax.set_title("标准化数据 + 主成分方向", color=colors["text"], fontsize=11, pad=8)
    ax.set_xlabel("X₁", color=colors["text"])
    ax.set_ylabel("X₂", color=colors["text"])
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2, color=colors["grid"])

    # Panel 2: Projected data
    ax = axes[1]
    ax.scatter(X_pca[:, 0], X_pca[:, 1], c="#cba6f7", s=15, alpha=0.7)
    ax.axhline(0, color=colors["grid"], lw=0.8)
    ax.axvline(0, color=colors["grid"], lw=0.8)
    ax.set_title("PCA 变换后", color=colors["text"], fontsize=11, pad=8)
    ax.set_xlabel("PC1", color=colors["text"])
    ax.set_ylabel("PC2", color=colors["text"])
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2, color=colors["grid"])

    # Panel 3: Variance bar
    ax = axes[2]
    bars = ax.bar(["PC1", "PC2"], ev * 100, color=["#f38ba8", "#a6e3a1"],
                  edgecolor="none", width=0.5)
    for bar, val in zip(bars, ev):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val*100:.1f}%", ha="center", color=colors["text"], fontsize=11, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_title("方差解释比例", color=colors["text"], fontsize=11, pad=8)
    ax.set_ylabel("%", color=colors["text"])
    ax.grid(True, axis="y", alpha=0.2, color=colors["grid"])

    fig.tight_layout(pad=2)
    img = fig_to_base64(fig, dpi=110)

    return jsonify({
        "image": img,
        "variance_ratio": [round(v*100, 2) for v in ev],
        "components": pca.components_.tolist(),
    })


@app.route("/api/real_data", methods=["POST"])
def api_real_data():
    """PCA on Iris or Wine dataset."""
    data = request.get_json()
    dataset_name = data.get("dataset", "iris")
    n_components = min(int(data.get("n_components", 2)), 10)

    if dataset_name == "wine":
        ds = load_wine()
    else:
        ds = load_iris()

    X = StandardScaler().fit_transform(ds.data)
    max_comp = min(X.shape[1], 10)
    n_components = min(n_components, max_comp)

    pca_full = PCA(n_components=max_comp)
    pca_full.fit(X)

    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X)

    colors_map = {0: "#f38ba8", 1: "#a6e3a1", 2: "#89b4fa"}
    label_names = ds.target_names

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    c = {"text": "#cdd6f4", "grid": "#45475a", "bg": "#1e1e2e"}
    for ax in axes:
        ax.set_facecolor(c["bg"])
        ax.tick_params(colors=c["text"])
        for sp in ax.spines.values():
            sp.set_color(c["grid"])

    # Scatter of first 2 PCs
    ax = axes[0]
    for label in np.unique(ds.target):
        mask = ds.target == label
        if n_components >= 2:
            ax.scatter(X_pca[mask, 0], X_pca[mask, 1], c=colors_map.get(label, "#cba6f7"),
                       s=18, alpha=0.75, label=label_names[label])
        else:
            ax.scatter(X_pca[mask, 0], np.zeros(mask.sum()), c=colors_map.get(label, "#cba6f7"),
                       s=18, alpha=0.75, label=label_names[label])
    ax.legend(fontsize=8, facecolor=c["bg"], edgecolor=c["grid"], labelcolor=c["text"])
    ax.set_title("PCA 投影（前2个主成分）", color=c["text"], fontsize=11, pad=8)
    ax.set_xlabel("PC1", color=c["text"])
    ax.set_ylabel("PC2" if n_components >= 2 else "", color=c["text"])
    ax.grid(True, alpha=0.2, color=c["grid"])

    # Scree plot
    ax = axes[1]
    evr = pca_full.explained_variance_ratio_ * 100
    x_vals = range(1, max_comp + 1)
    ax.bar(x_vals, evr, color="#89b4fa", edgecolor="none", alpha=0.7)
    ax.plot(x_vals, evr, "o-", color="#f38ba8", markersize=5, lw=1.5)
    ax.axvline(n_components + 0.5, color="#f9e2af", ls="--", lw=1.5, label=f"选取 {n_components} 个")
    ax.legend(fontsize=8, facecolor=c["bg"], edgecolor=c["grid"], labelcolor=c["text"])
    ax.set_title("碎石图（Scree Plot）", color=c["text"], fontsize=11, pad=8)
    ax.set_xlabel("主成分编号", color=c["text"])
    ax.set_ylabel("方差解释 %", color=c["text"])
    ax.grid(True, axis="y", alpha=0.2, color=c["grid"])

    # Cumulative variance
    ax = axes[2]
    cum = np.cumsum(evr)
    ax.plot(x_vals, cum, "o-", color="#cba6f7", lw=2, markersize=5)
    ax.fill_between(x_vals, cum, alpha=0.15, color="#cba6f7")
    ax.axhline(90, color="#f9e2af", ls="--", lw=1, alpha=0.7)
    ax.text(max_comp * 0.7, 92, "90%", color="#f9e2af", fontsize=9)
    ax.axvline(n_components, color="#a6e3a1", ls="--", lw=1.5)
    total_var = float(sum(pca.explained_variance_ratio_) * 100)
    ax.text(n_components + 0.3, total_var - 5, f"{total_var:.1f}%",
            color="#a6e3a1", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.set_title("累积方差解释", color=c["text"], fontsize=11, pad=8)
    ax.set_xlabel("主成分数量", color=c["text"])
    ax.set_ylabel("累积 %", color=c["text"])
    ax.grid(True, alpha=0.2, color=c["grid"])

    fig.tight_layout(pad=2)
    img = fig_to_base64(fig, dpi=110)

    return jsonify({
        "image": img,
        "total_variance": round(total_var, 2),
        "individual_variance": [round(v, 2) for v in evr[:n_components]],
        "n_features": X.shape[1],
        "n_samples": X.shape[0],
        "feature_names": list(ds.feature_names),
    })


@app.route("/api/faces", methods=["POST"])
def api_faces():
    """PCA on face images - reconstruction with varying components."""
    data = request.get_json()
    n_components = min(int(data.get("n_components", 10)), 40)
    face_idx = min(int(data.get("face_idx", 0)), 39)

    X = get_faces()
    mean_face = X.mean(axis=0)
    X_centered = X - mean_face

    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_centered)

    reconstructed = pca.inverse_transform(X_pca) + mean_face
    recon_face = reconstructed[face_idx].reshape(64, 64)
    orig_face = X[face_idx].reshape(64, 64)
    mean_face_img = mean_face.reshape(64, 64)

    total_var = float(sum(pca.explained_variance_ratio_) * 100)

    # Eigenfaces (first few components)
    n_show = min(n_components, 8)
    eigenfaces = []
    for i in range(n_show):
        ef = pca.components_[i].reshape(64, 64)
        ef_norm = (ef - ef.min()) / (ef.max() - ef.min() + 1e-8)
        eigenfaces.append(np_img_to_base64(ef_norm, size=(128, 128)))

    # Reconstruction steps
    recon_steps = []
    step_counts = [1, 2, 5, 10, 20, n_components] if n_components >= 20 else \
                  [1, 2, max(3, n_components//3), max(5, n_components//2), n_components]
    step_counts = sorted(set(min(s, n_components) for s in step_counts))

    for nc in step_counts:
        pca_step = PCA(n_components=nc)
        pca_step.fit(X_centered)
        step_recon = pca_step.inverse_transform(pca_step.transform(X_centered)) + mean_face
        step_face = step_recon[face_idx].reshape(64, 64)
        var_step = float(sum(pca_step.explained_variance_ratio_) * 100)
        recon_steps.append({
            "n": int(nc),
            "image": np_img_to_base64(step_face, size=(128, 128)),
            "variance": round(var_step, 1),
        })

    # Scree
    pca_full = PCA(n_components=min(40, X.shape[0]))
    pca_full.fit(X_centered)
    evr_full = pca_full.explained_variance_ratio_ * 100

    fig, ax = plt.subplots(1, 1, figsize=(6, 3.5))
    c = {"text": "#cdd6f4", "grid": "#45475a", "bg": "#1e1e2e"}
    ax.set_facecolor(c["bg"])
    fig.patch.set_facecolor(c["bg"])
    ax.tick_params(colors=c["text"])
    for sp in ax.spines.values():
        sp.set_color(c["grid"])

    x_vals = range(1, len(evr_full) + 1)
    ax.bar(x_vals, evr_full, color="#89b4fa", edgecolor="none", alpha=0.6)
    cum = np.cumsum(evr_full)
    ax2 = ax.twinx()
    ax2.plot(x_vals, cum, "o-", color="#cba6f7", lw=2, markersize=3)
    ax2.set_ylim(0, 105)
    ax2.tick_params(colors=c["text"])
    ax2.set_ylabel("累积 %", color=c["text"], fontsize=9)
    for sp in ax2.spines.values():
        sp.set_color(c["grid"])
    ax.axvline(n_components + 0.5, color="#f9e2af", ls="--", lw=1.5)
    ax.set_xlabel("主成分编号", color=c["text"], fontsize=9)
    ax.set_ylabel("方差解释 %", color=c["text"], fontsize=9)
    ax.set_title(f"人脸数据碎石图（选取 {n_components} 个主成分，累积 {total_var:.1f}%）",
                 color=c["text"], fontsize=10, pad=8)
    ax.grid(True, axis="y", alpha=0.2, color=c["grid"])
    fig.tight_layout(pad=1.5)
    scree_img = fig_to_base64(fig, dpi=100)

    return jsonify({
        "original": np_img_to_base64(orig_face, size=(128, 128)),
        "mean_face": np_img_to_base64(mean_face_img, size=(128, 128)),
        "reconstructed": np_img_to_base64(recon_face, size=(128, 128)),
        "eigenfaces": eigenfaces,
        "recon_steps": recon_steps,
        "scree": scree_img,
        "total_variance": round(total_var, 1),
        "n_components": n_components,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
