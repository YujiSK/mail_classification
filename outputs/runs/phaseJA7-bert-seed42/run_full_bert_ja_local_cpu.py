"""Full 5-fold DistilBERT/BERT-ja fine-tune comparison for Task10-JA.

Runs entirely outside the task10 project's own uv environment (isolated
Python 3.12 venv in this scratchpad), so torch/transformers never touch
task10/uv.lock. Reads the same Full data and common Fold artifact the Core
J0-JC experiments used, verified by hash, and writes artifacts in a schema
matching the English Phase 8 DistilBERT comparison
(outputs/runs/phase8-bert-seed42/) as closely as possible.
"""

import hashlib
import json
import platform
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path("/home/rb132/Desktop/Sunagawa/nlp_preprocessing/task10")
DATA_PATH = ROOT / "data" / "raw" / "full_emails_ja.jsonl"
FOLD_PATH = ROOT / "outputs" / "folds" / "common_folds_ja.json"
OUT_DIR = ROOT / "outputs" / "runs" / "phaseJA7-bert-seed42"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "tohoku-nlp/bert-base-japanese-v3"
LABELS = ["product_inquiry", "technical_issue", "billing", "account_support"]
LABEL2ID = {label: index for index, label in enumerate(LABELS)}
SEED = 42
MAX_LEN = 128
BATCH_SIZE = 16
EPOCHS = 3
LEARNING_RATE = 2e-5

torch.manual_seed(SEED)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TextDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.texts, self.labels, self.tokenizer, self.max_len = texts, labels, tokenizer, max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, index):
        encoding = self.tokenizer(
            self.texts[index],
            truncation=True,
            max_length=self.max_len,
            padding="max_length",
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoding.items()}
        item["labels"] = torch.tensor(self.labels[index])
        return item


def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        batch = {key: value.to(device) for key, value in batch.items()}
        outputs = model(**batch)
        outputs.loss.backward()
        optimizer.step()
        total_loss += outputs.loss.item()
    return total_loss / max(len(loader), 1)


def evaluate(model, loader, device):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            preds = outputs.logits.argmax(dim=-1).cpu()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.tolist())
    return all_labels, all_preds


def main():
    print("data_hash:", sha256_file(DATA_PATH))
    print("fold_hash:", sha256_file(FOLD_PATH))

    records = [json.loads(line) for line in DATA_PATH.read_text(encoding="utf-8").splitlines()]
    records_by_id = {record["id"]: record for record in records}

    fold_artifact = json.loads(FOLD_PATH.read_text(encoding="utf-8"))
    n_splits = fold_artifact["metadata"]["n_splits"]
    fold_rows = fold_artifact["records"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device:", device)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    fold_metrics = []
    oof_rows = []
    run_start = time.time()

    for fold_id in range(n_splits):
        fold_start = time.time()
        train_ids = [
            row["sample_id"]
            for row in fold_rows
            if row["fold_id"] == fold_id and row["split_role"] == "train"
        ]
        val_ids = [
            row["sample_id"]
            for row in fold_rows
            if row["fold_id"] == fold_id and row["split_role"] == "validation"
        ]

        train_texts = [records_by_id[sid]["body_text"] for sid in train_ids]
        train_labels = [LABEL2ID[records_by_id[sid]["label"]] for sid in train_ids]
        val_texts = [records_by_id[sid]["body_text"] for sid in val_ids]
        val_labels = [LABEL2ID[records_by_id[sid]["label"]] for sid in val_ids]

        torch.manual_seed(SEED)
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME, num_labels=len(LABELS)
        )
        model.to(device)
        optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)

        train_loader = DataLoader(
            TextDataset(train_texts, train_labels, tokenizer, MAX_LEN),
            batch_size=BATCH_SIZE,
            shuffle=True,
        )
        val_loader = DataLoader(
            TextDataset(val_texts, val_labels, tokenizer, MAX_LEN),
            batch_size=BATCH_SIZE,
            shuffle=False,
        )

        for epoch in range(EPOCHS):
            epoch_loss = train_epoch(model, train_loader, optimizer, device)
            print(
                f"fold={fold_id} epoch={epoch} loss={epoch_loss:.4f} "
                f"elapsed={time.time() - fold_start:.1f}s",
                flush=True,
            )

        true_ids_order = val_ids
        y_true_ids, y_pred_ids = evaluate(model, val_loader, device)
        y_true = [LABELS[i] for i in y_true_ids]
        y_pred = [LABELS[i] for i in y_pred_ids]

        accuracy = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="macro", labels=LABELS, zero_division=0
        )
        cw_precision, cw_recall, cw_f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=LABELS, zero_division=0
        )
        fold_seconds = time.time() - fold_start
        row = {
            "fold_id": fold_id,
            "n_train": len(train_ids),
            "n_val": len(val_ids),
            "accuracy": accuracy,
            "macro_precision": precision,
            "macro_recall": recall,
            "macro_f1": f1,
            "fold_seconds": fold_seconds,
        }
        for label, p, r, f in zip(LABELS, cw_precision, cw_recall, cw_f1):
            row[f"precision_{label}"] = p
            row[f"recall_{label}"] = r
            row[f"f1_{label}"] = f
        fold_metrics.append(row)
        print("fold result:", row, flush=True)

        for sample_id, true_label, predicted_label in zip(true_ids_order, y_true, y_pred):
            oof_rows.append(
                {
                    "sample_id": sample_id,
                    "condition": "bert_ja",
                    "model": "tohoku-nlp-bert-base-japanese-v3",
                    "fold_id": fold_id,
                    "true_label": true_label,
                    "predicted_label": predicted_label,
                }
            )

        # persist incrementally in case of interruption
        (OUT_DIR / "fold_metrics.json").write_text(
            json.dumps(fold_metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (OUT_DIR / "predictions_oof.json").write_text(
            json.dumps(oof_rows, ensure_ascii=False), encoding="utf-8"
        )
        del model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

    total_seconds = time.time() - run_start

    import csv

    with (OUT_DIR / "fold_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fold_metrics[0].keys()))
        writer.writeheader()
        writer.writerows(fold_metrics)

    with (OUT_DIR / "predictions_oof.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(oof_rows[0].keys()))
        writer.writeheader()
        writer.writerows(oof_rows)

    import sklearn
    import transformers as transformers_module

    manifest = {
        "run_id": "phaseJA7-bert-seed42",
        "model_name": MODEL_NAME,
        "language": "ja",
        "data_path": str(DATA_PATH.relative_to(ROOT)),
        "data_hash": sha256_file(DATA_PATH),
        "fold_artifact_path": str(FOLD_PATH.relative_to(ROOT)),
        "fold_artifact_hash": sha256_file(FOLD_PATH),
        "n_splits": n_splits,
        "seed": SEED,
        "max_length": MAX_LEN,
        "batch_size": BATCH_SIZE,
        "effective_batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "input_field": "body_text",
        "device": str(device),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "transformers_version": transformers_module.__version__,
        "sklearn_version": sklearn.__version__,
        "total_training_seconds": total_seconds,
        "primary_metric": "macro_f1",
        "execution_environment": "local_cpu_isolated_venv_python3.12",
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("DONE. total_seconds:", total_seconds)


if __name__ == "__main__":
    main()
