# backend/run_backend.py
import subprocess
import sys
import os

# Get the path to the virtual environment's uvicorn executable
# Assumes venv is in 'backend/venv'
uvicorn_executable = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "venv", "Scripts", "uvicorn.exe" # For Windows
)

if not os.path.exists(uvicorn_executable):
    print(f"Error: uvicorn executable not found at {uvicorn_executable}")
    print("Please ensure your virtual environment is set up and uvicorn is installed.")
    sys.exit(1)

command = [
    uvicorn_executable,
    "main:app",
    "--reload",
    "--host", "0.0.0.0",
    "--port", "8000"
]

print(f"Starting backend with command: {' '.join(command)}")

# Pass environment variables (if any, like Tesseract path or AWS credentials)
# The current process's environment variables are automatically inherited
# for subprocesses in Python, so if you set AWS_ACCESS_KEY_ID etc.
# in the PowerShell session *before* running this script, it will work.

try:
    # Start the uvicorn process
    process = subprocess.Popen(command)
    process.wait() # Wait for the process to exit
except KeyboardInterrupt:
    print("\nBackend stopped by user.")
    process.terminate()
except Exception as e:
    print(f"An error occurred: {e}")
sys.exit(0)