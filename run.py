#!/usr/bin/env python3
"""
Direct launcher for ETDS Dashboard
Run this with: python run.py
Or double-click it if Python is associated with .py files
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    project_dir = Path(__file__).parent
    setup_script = project_dir / "setup.py"

    print("=" * 60)
    print("ETDS PDF Renamer — Dashboard Launcher")
    print("=" * 60)

    if not setup_script.exists():
        print("ERROR: setup.py not found!")
        sys.exit(1)

    # Run setup
    result = subprocess.run([sys.executable, str(setup_script)])
    sys.exit(result.returncode)
