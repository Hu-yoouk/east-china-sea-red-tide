"""检查两个模型目录的测试日期、标签和预测概率是否一致。"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    reference = pd.read_csv(args.reference / "test_predictions.csv")
    candidate = pd.read_csv(args.candidate / "test_predictions.csv")
    if not reference[["target_month", "true_label"]].equals(candidate[["target_month", "true_label"]]):
        parser.exit(2, "复现失败：测试月份或标签不一致\n")
    np.testing.assert_allclose(reference.probability, candidate.probability, atol=1e-8, rtol=0)
    print("复现通过：测试日期、标签和概率一致，绝对误差不超过 1e-8。")


if __name__ == "__main__":
    main()
