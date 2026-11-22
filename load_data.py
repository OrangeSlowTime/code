"""数据清洗与入库脚本：把 CSV 写入 SQLite（tmall.db），并做商品去重。

用法：
    python load_data.py
"""
import glob
import os
import sqlite3

import pandas as pd

import config


def _find_csv_files():
    files = sorted(glob.glob(os.path.join(config.CSV_DIR, "*.csv")))
    if files:
        return files
    if os.path.exists(config.CSV_FALLBACK):
        return [config.CSV_FALLBACK]
    raise FileNotFoundError(
        f"未找到数据文件：请放到 {config.CSV_DIR}/ 或 {config.CSV_FALLBACK}"
    )


def _parse_sales(value):
    """'7000+' / '1.8万+' -> 数值。"""
    if pd.isna(value):
        return None
    text = str(value).strip().replace("+", "")
    if text == "":
        return None
    try:
        if "万" in text:
            return float(text.replace("万", "")) * 10000
        return float(text)
    except ValueError:
        return None


def load_dataframe():
    frames = []
    for path in _find_csv_files():
        print(f"读取数据文件: {path}")
        frames.append(pd.read_csv(path, dtype=str, encoding="utf-8-sig"))

    df = pd.concat(frames, ignore_index=True)
    if "基础销量（无效）" in df.columns:
        df = df.drop(columns=["基础销量（无效）"])

    if "年销量" in df.columns:
        df["年销量"] = df["年销量"].apply(_parse_sales)

    for column in config.NUMERIC_COLUMNS:
        if column in df.columns and column != "年销量":
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].str.strip().replace({"": None})

    raw_count = len(df)

    # 去重：同一商品可能被多次采集，保留最新采集的一条
    if "采集时间" in df.columns:
        df = df.sort_values("采集时间", ascending=False, na_position="last")
    if "商品ID" in df.columns:
        df = df.drop_duplicates(subset=["商品ID"], keep="first")
    df = df.drop_duplicates(subset=["商品标题", "店铺名称"], keep="first")

    print(f"原始 {raw_count:,} 行，去重后 {len(df):,} 行。")
    return df


def main():
    df = load_dataframe()
    conn = sqlite3.connect(config.DB_PATH)
    df.to_sql(config.TABLE_NAME, conn, if_exists="replace", index=False)
    cur = conn.cursor()
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_brand ON {config.TABLE_NAME}(品牌名称)"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cat1 ON {config.TABLE_NAME}(一级类目名称)"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cat2 ON {config.TABLE_NAME}(二级类目名称)"
    )
    conn.commit()
    total = cur.execute(f"SELECT COUNT(*) FROM {config.TABLE_NAME}").fetchone()[0]
    conn.close()
    print(f"入库完成: {config.DB_PATH}，共 {total:,} 行。")


if __name__ == "__main__":
    main()
