from pathlib import Path

#obtener la ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent

#configuración de directorios
VIDEOS_ORIGINAL_DIR = BASE_DIR / "videos_original"
OUTPUT_VIDEOS_DIR = BASE_DIR / "output_videos"
METADATA_DIR = BASE_DIR / "metadata"
MODELS_DIR = BASE_DIR / "models"

#ruta del archivo list_release2.0.txt
LIST_FILE = BASE_DIR / "list_release2.0.txt"

#asegurar que los directorios existan
VIDEOS_ORIGINAL_DIR.mkdir(exist_ok=True)
OUTPUT_VIDEOS_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

#configuración de la API
API_HOST = "127.0.0.1"
API_PORT = 8000

# Configuración de la base de datos
DATABASE_PATH = BASE_DIR / "metadata.db"

# Configuración del modelo YOLO
MODEL_PATH = MODELS_DIR / "yolov8n.pt"