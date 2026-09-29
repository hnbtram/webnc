"""Chuẩn bị artifacts: tải dữ liệu, huấn luyện classifier, tải YOLO, build FAISS index.
Chạy: python backend/scripts/prepare_artifacts.py
"""
import json
import random
import shutil
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from PIL import Image
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision.datasets import ImageFolder

from config import ART_DIR, DATA_DIR, DEVICE
import core.classifier as clf
import core.detector as det
import core.retrieval as ret

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
FAST = DEVICE == "cpu"


def download(url: str, dest: Path) -> Path:
    dest = Path(dest)
    if not dest.exists():
        print("↓", url)
        urllib.request.urlretrieve(url, dest)
    return dest


# ---- 1) TF Flowers ----
FLOWERS_DIR = DATA_DIR / "flowers" / "flower_photos"
if not FLOWERS_DIR.exists():
    tgz = download("https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz",
                   DATA_DIR / "flower_photos.tgz")
    with tarfile.open(tgz) as t:
        t.extractall(DATA_DIR / "flowers", filter="data")
    tgz.unlink()
(FLOWERS_DIR / "LICENSE.txt").unlink(missing_ok=True)

# ---- 2) COCO128 ----
COCO_DIR = DATA_DIR / "coco128"
if not COCO_DIR.exists():
    z = download("https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip", DATA_DIR / "coco128.zip")
    with zipfile.ZipFile(z) as f:
        f.extractall(DATA_DIR)
    z.unlink()
COCO_IMAGES = sorted((COCO_DIR / "images" / "train2017").glob("*.jpg"))
print("COCO128:", len(COCO_IMAGES), "ảnh")

# ---- 3) Huấn luyện classifier ----
base = ImageFolder(FLOWERS_DIR)
classes, targets = base.classes, np.array(base.targets)
all_idx = np.arange(len(targets))
train_idx, tmp_idx = train_test_split(all_idx, test_size=0.2, stratify=targets, random_state=SEED)
val_idx, test_idx = train_test_split(tmp_idx, test_size=0.5, stratify=targets[tmp_idx], random_state=SEED)
if FAST:
    train_idx = np.random.default_rng(SEED).choice(train_idx, size=min(800, len(train_idx)), replace=False)

train_ds = Subset(ImageFolder(FLOWERS_DIR, transform=clf.TRAIN_TF), train_idx)
val_ds = Subset(ImageFolder(FLOWERS_DIR, transform=clf.EVAL_TF), val_idx)
test_ds = Subset(ImageFolder(FLOWERS_DIR, transform=clf.EVAL_TF), test_idx)
loader = lambda ds, shuffle: DataLoader(ds, batch_size=64, shuffle=shuffle, num_workers=2, pin_memory=DEVICE == "cuda")
train_dl, val_dl, test_dl = loader(train_ds, True), loader(val_ds, False), loader(test_ds, False)

EPOCHS = 1 if FAST else 5
model = clf.build_model(len(classes)).to(DEVICE)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=1e-3, total_steps=EPOCHS * len(train_dl))
use_amp = DEVICE == "cuda"
scaler = torch.amp.GradScaler("cuda", enabled=use_amp)


def run_epoch(dl, train: bool):
    model.train(train)
    total, correct, loss_sum = 0, 0, 0.0
    for x, y in dl:
        x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
        with torch.set_grad_enabled(train), torch.autocast(DEVICE, dtype=torch.float16, enabled=use_amp):
            logits = model(x)
            loss = criterion(logits, y)
        if train:
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer); scaler.update(); scheduler.step()
        loss_sum += loss.item() * len(y); correct += (logits.argmax(1) == y).sum().item(); total += len(y)
    return loss_sum / total, correct / total


best_acc, history = 0.0, []
for epoch in range(1, EPOCHS + 1):
    t0 = time.time()
    tr_loss, tr_acc = run_epoch(train_dl, True)
    va_loss, va_acc = run_epoch(val_dl, False)
    history.append({"epoch": epoch, "train_loss": tr_loss, "train_acc": tr_acc, "val_loss": va_loss, "val_acc": va_acc})
    if va_acc > best_acc:
        best_acc = va_acc
        torch.save(model.state_dict(), ART_DIR / "classifier" / "model.pt")
    print(f"epoch {epoch}/{EPOCHS} · train {tr_acc:.3f} · val {va_acc:.3f} · {time.time()-t0:.0f}s")

(ART_DIR / "classifier" / "classes.json").write_text(json.dumps(classes))
(ART_DIR / "classifier" / "metrics.json").write_text(json.dumps(
    {"val_accuracy": best_acc, "epochs": EPOCHS, "history": history}, indent=2))
print("Classifier xong. Val acc =", round(best_acc, 4))

# ---- 4) Tải YOLO ----
from ultralytics.utils.downloads import attempt_download_asset
attempt_download_asset(str(ART_DIR / "detector" / "yolo11n.pt"))
print("YOLO xong.")

# ---- 5) Build gallery + FAISS index ----
detector = det.ObjectDetector()
GALLERY = DATA_DIR / "gallery"
GALLERY.mkdir(exist_ok=True)
items = []
for p in COCO_IMAGES:
    summary = detector.detect(Image.open(p), conf=0.4)[0]["summary"]
    label = ", ".join(sorted(summary, key=summary.get, reverse=True)[:2]) or "coco"
    dst = GALLERY / f"coco_{p.name}"; shutil.copy(p, dst)
    items.append({"path": str(dst.relative_to(ROOT)), "label": label, "source": "coco128"})
rng = random.Random(SEED)
for c in classes:
    files = sorted((FLOWERS_DIR / c).glob("*.jpg"))
    for p in rng.sample(files, min(100, len(files))):
        dst = GALLERY / f"{c}_{p.name}"; shutil.copy(p, dst)
        items.append({"path": str(dst.relative_to(ROOT)), "label": c, "source": "flowers"})

encoder = ret.ClipEncoder()
t0 = time.time()
ret.build_index(encoder, items)
print(f"Đã lập chỉ mục {len(items)} ảnh trong {time.time() - t0:.0f}s")
print("✅ Hoàn tất tất cả artifacts.")