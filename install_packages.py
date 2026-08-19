import sys
import subprocess

packages = [
    "Flask==3.0.3",
    "qrcode==7.4.2",
    "Pillow==10.4.0",
    "WeasyPrint==61.2"
]

print("Python executable:")
print(sys.executable)

print("Python version:")
print(sys.version)

print("\nInstalling packages...\n")

for package in packages:
    print("\n====================================")
    print("Installing:", package)
    print("====================================")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )

    print(result.stdout)
    print("Exit code:", result.returncode)

print("\nFinished.")
