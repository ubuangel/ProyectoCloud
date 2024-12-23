from pathlib import Path

#obtener la ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent

#configuración de directorios
VIDEOS_ORIGINAL_DIR = BASE_DIR / "videos_original"
OUTPUT_VIDEOS_DIR = BASE_DIR / "output_videos"
METADATA_DIR = BASE_DIR / "metadata"
MODELS_DIR = BASE_DIR / "models"
print(BASE_DIR)
print(" ..")
print(MODELS_DIR)