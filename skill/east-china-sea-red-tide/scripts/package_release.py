"""生成可分享的完整技能包，并在压缩包内写入逐文件 SHA256 清单。"""

import argparse
import hashlib
import json
import os
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = args.output.resolve()
    if target == root or root in target.parents:
        parser.exit(2, "压缩包必须保存在仓库外，避免递归打包自身。\n")
    excluded = {".venv", ".git", "node_modules", "__pycache__", "outputs", "dist", "build", "local_data"}
    files = []
    for directory, names, leaves in os.walk(root):
        names[:] = [name for name in names if name not in excluded and not name.endswith(".egg-info")]
        for name in leaves:
            path = Path(directory) / name
            if path.is_symlink() or name.startswith(".env") or path.suffix in {".pyc", ".log", ".tsbuildinfo"}:
                continue
            files.append(path)
    manifest = {}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            manifest[relative] = hashlib.sha256(data).hexdigest()
            archive.writestr(f"{root.name}/{relative}", data)
        archive.writestr(f"{root.name}/MANIFEST.sha256.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            parser.exit(2, "压缩包完整性检查失败。\n")
    print(f"已打包 {len(files)} 个文件，{target.stat().st_size / 1024 / 1024:.2f} MiB：{target}")


if __name__ == "__main__":
    main()
