"""
build_helper.py
Goi Nuitka voi dung arguments - tranh moi van de quoting cua CMD.
Chay: python build_helper.py
"""
import subprocess
import sys
import pathlib

root = pathlib.Path(__file__).parent.resolve()
dist = root / "dist"
dist.mkdir(exist_ok=True)

print("[Nuitka] Starting build...")
print(f"[Nuitka] Root   : {root}")
print(f"[Nuitka] Output : {dist / 'AIShorts.exe'}")
print()

# Kiem tra cac thu muc can thiet
required_dirs = ["engine", "tests"]
for d in required_dirs:
    p = root / d
    if not p.exists():
        print(f"[WARNING] Directory not found, skipping: {p}")

args = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--windows-console-mode=disable",
    f"--windows-icon-from-ico={root / 'logo.ico'}",
    "--enable-plugin=pyqt5",
    "--assume-yes-for-downloads",
]

# Khong can bundle data files vao exe (vi Inno Setup se copy chung vao thu muc cai dat)

args += [
    f"--output-dir={dist}",
    "--output-filename=AIShorts.exe",
    "--company-name=AI Shorts Generator",
    "--product-name=AI Shorts Generator",
    "--file-version=1.0.0.0",
    "--product-version=1.0.0.0",
    "--file-description=AI Shorts Generator",
    "--copyright=Copyright 2025",
    str(root / "gui.py"),
]

print("[Nuitka] Arguments:")
for a in args[2:]:
    print(f"         {a}")
print()

result = subprocess.run(args, cwd=str(root))
sys.exit(result.returncode)
