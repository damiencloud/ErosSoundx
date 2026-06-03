import os
import subprocess
import shutil
import sys

def main():
    print("=========================================")
    print("      EROSSOUNDX EXECUTABLE BUILDER      ")
    print("=========================================\n")

    # 1. Verify environment
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    icon_path = os.path.join("assets", "icon.ico")
    version_file = "version_info.txt"

    if not os.path.exists(icon_path):
        print(f"Error: Icon asset not found at {icon_path}. Build aborted.")
        sys.exit(1)

    if not os.path.exists(version_file):
        print(f"Error: Version resource template not found at {version_file}. Build aborted.")
        sys.exit(1)

    # 2. Build pyinstaller command
    print("Building ErosSoundX with PyInstaller...")
    cmd = [
        "pyinstaller",
        "--noconsole",
        f"--icon={icon_path}",
        f"--version-file={version_file}",
        "--add-data", "src/web;src/web",
        "--add-data", "assets;assets",
        "--name=ErosSoundX",
        "--clean",
        "main.py"
    ]

    print("Running command: " + " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        print("\nPyInstaller build completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nError: PyInstaller compilation failed with code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print("\nError: pyinstaller executable not found in PATH. Please run 'pip install pyinstaller' first.")
        sys.exit(1)

    # 3. Cleanup intermediate folders
    print("\nCleaning up intermediate build artifacts...")
    spec_path = "ErosSoundX.spec"
    build_dir = "build"
    
    if os.path.exists(spec_path):
        os.remove(spec_path)
        print(f"Removed {spec_path}")
        
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print(f"Removed {build_dir}/ directory")

    print("\n=========================================")
    print("  Build Success! Standalone binary is at:")
    print("  dist/ErosSoundX/ErosSoundX.exe")
    print("=========================================")

if __name__ == "__main__":
    main()
