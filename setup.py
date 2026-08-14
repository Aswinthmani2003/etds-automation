#!/usr/bin/env python3
"""
ETDS PDF Renamer — Universal Setup Script
Installs all dependencies and runs the app
Works on any system with Python installed
"""

import os
import sys
import subprocess
import venv
import shutil
from pathlib import Path

# Colors for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(msg):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{msg}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}→ {msg}{RESET}")

def run_command(cmd, description=""):
    """Run a shell command and handle errors"""
    if description:
        print_info(description)
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            if result.stderr:
                print(f"  Error: {result.stderr}")
            return False
        if result.stdout:
            print(f"  {result.stdout.strip()}")
        return True
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out: {cmd}")
        return False
    except Exception as e:
        print_error(f"Failed to run command: {e}")
        return False

def main():
    print_header("ETDS PDF Renamer — Universal Setup")

    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    # Step 1: Check Python version
    print_header("Step 1: Checking Python")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print_success(f"Python {py_version} found")

    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 8):
        print_error(f"Python 3.8+ required, but {py_version} found")
        sys.exit(1)

    # Step 2: Create/use virtual environment
    print_header("Step 2: Setting up virtual environment")
    venv_path = project_dir / "venv"

    if venv_path.exists():
        print_info("Deleting old virtual environment...")
        shutil.rmtree(venv_path)

    print_info("Creating virtual environment...")
    try:
        venv.create(venv_path, with_pip=True)
        print_success("Virtual environment created")
    except Exception as e:
        print_error(f"Failed to create venv: {e}")
        sys.exit(1)

    # Determine pip command based on OS
    if sys.platform == "win32":
        pip_cmd = str(venv_path / "Scripts" / "pip.exe")
        python_cmd = str(venv_path / "Scripts" / "python.exe")
    else:
        pip_cmd = str(venv_path / "bin" / "pip")
        python_cmd = str(venv_path / "bin" / "python")

    # Step 3: Upgrade pip
    print_header("Step 3: Upgrading pip")
    if not run_command(f'"{pip_cmd}" install --upgrade pip --quiet', "Upgrading pip..."):
        print_error("Failed to upgrade pip, but continuing anyway...")
    else:
        print_success("pip upgraded")

    # Step 4: Install packages from requirements.txt
    print_header("Step 4: Installing required packages")

    requirements_file = project_dir / "requirements.txt"
    if not requirements_file.exists():
        print_error("requirements.txt not found!")
        sys.exit(1)

    print_info("Installing all packages from requirements.txt...")
    cmd = f'"{pip_cmd}" install -r "{requirements_file}"'
    if not run_command(cmd, "Running: pip install -r requirements.txt"):
        print_error("Package installation failed.")
        print_info("Retrying with verbose output...")
        cmd = f'"{pip_cmd}" install -r "{requirements_file}" --verbose'
        if not run_command(cmd):
            print_error("Installation failed. Check your internet connection.")
            sys.exit(1)

    print_success("All packages installed")

    # Step 5: Verify installation
    print_header("Step 5: Verifying installation")

    test_imports = [
        "flask",
        "flask_compress",
        "pymupdf",
        "zxingcpp",
        "PIL",
        "openpyxl",
        "xlrd",
        "gunicorn"
    ]

    all_good = True
    for module in test_imports:
        cmd = f'"{python_cmd}" -c "import {module}"'
        if run_command(cmd, f"Checking {module}..."):
            print_success(f"{module} ✓")
        else:
            print_error(f"{module} ✗")
            all_good = False

    if not all_good:
        print_error("\nSome packages are missing!")
        print_info("Try running this script again or check your internet connection")
        sys.exit(1)

    print_success("\nAll packages verified successfully!")

    # Step 6: Launch dashboard
    print_header("Step 6: Starting dashboard")
    print_success("All packages ready!")
    print_info("Launching dashboard at http://localhost:5000")
    print_info("Press Ctrl+C to stop the server")
    print()

    # Open browser if on Windows
    if sys.platform == "win32":
        try:
            import webbrowser
            webbrowser.open("http://localhost:5000")
        except:
            pass

    # Run app
    try:
        subprocess.run(f'"{python_cmd}" app.py', shell=True)
    except KeyboardInterrupt:
        print_success("\nServer stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
