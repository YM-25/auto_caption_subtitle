import subprocess
import sys
import os
import importlib.util

def check_and_install_dependencies():
    """
    Check that required packages from requirements.txt are importable;
    if any are missing, run pip install -r requirements.txt and exit on failure.

    Intended to be called once at application startup (e.g. from app.py when
    running the server). Package name parsing is best-effort (==, >=, <=, [);
    for complex version specs, rely on pip -r requirements.txt.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req_file = os.path.join(base_dir, "requirements.txt")
    
    if not os.path.exists(req_file):
        print(f"Warning: requirements.txt not found at {req_file}")
        return

    print("Checking dependencies...")
    
    with open(req_file, "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    missing = []
    for req in requirements:
        # Simple package name extraction (handles 'flask==2.3.3' or 'openai-whisper')
        pkg_name = req.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0].strip()
        
        # Whisper is imported as 'whisper' but package is 'openai-whisper'
        import_name = pkg_name
        if pkg_name == "openai-whisper":
            import_name = "whisper"
        elif pkg_name == "ffmpeg-python":
            import_name = "ffmpeg"
        
        if importlib.util.find_spec(import_name) is None:
            missing.append(req)

    if missing:
        print(f"Missing dependencies found: {', '.join(missing)}")
        print("Installing missing packages...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("Dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            sys.exit(1)
    else:
        print("All dependencies are already installed.")

if __name__ == "__main__":
    check_and_install_dependencies()
