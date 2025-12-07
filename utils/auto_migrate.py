import subprocess
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_migrations():
    """
    Menjalankan Alembic upgrade head setiap kali FastAPI startup.
    Tidak memblok browser, dan aman untuk Railway.
    """
    try:
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=BASE_DIR,
            check=True
        )
        print("Alembic migration executed successfully.")
    except subprocess.CalledProcessError as e:
        print("Alembic migration failed:", e)
