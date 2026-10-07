
import argparse
import hashlib
import os
import time
from pathlib import Path

import pandas as pd
import requests


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    log_rows = []

    print("Metadata rows:", len(df))
    print("Classes:", df["label"].nunique())
    print("Output:", out_dir)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    for i, row in df.iterrows():

        url = row.get("url")
        label = str(row["label"])
        expected_md5 = str(row["md5hash"])

        class_dir = out_dir / label
        class_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{expected_md5}.jpg"
        save_path = class_dir / filename

        # Resume support
        if save_path.exists():
            current_md5 = md5_file(save_path)

            if current_md5 == expected_md5:
                status = "already_valid"
                log_rows.append({
                    "index": i,
                    "label": label,
                    "url": url,
                    "file": str(save_path),
                    "status": status
                })
                continue
            else:
                save_path.unlink()

        if pd.isna(url) or not str(url).startswith("http"):
            status = "missing_url"

        else:
            try:
                r = session.get(url, timeout=20)
                r.raise_for_status()

                save_path.write_bytes(r.content)

                downloaded_md5 = md5_file(save_path)

                if downloaded_md5 == expected_md5:
                    status = "success"
                else:
                    status = "md5_mismatch"
                    save_path.unlink(missing_ok=True)

            except Exception as e:
                status = f"failed: {type(e).__name__}"

        log_rows.append({
            "index": i,
            "label": label,
            "url": url,
            "file": str(save_path),
            "status": status
        })

        if (i + 1) % 100 == 0:
            print(f"{i + 1}/{len(df)} processed")

        time.sleep(args.delay)

    log_df = pd.DataFrame(log_rows)
    log_path = out_dir / "download_log.csv"
    log_df.to_csv(log_path, index=False)

    print("\nFinished.")
    print(log_df["status"].value_counts())
    print("\nLog saved to:", log_path)


if __name__ == "__main__":
    main()
