from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from PIL import Image
import numpy as np
import json
import cv2
import os
from config import *
from database import insert_or_update_video_data
import logging

logger = logging.getLogger(__name__)

heatmap_router = APIRouter()

@heatmap_router.get("/{video_name}")
async def get_heatmap(video_name: str, background_tasks: BackgroundTasks):
    try:
        heatmap_path = OUTPUT_VIDEOS_DIR / f"heatmap_{video_name.replace('.mp4', '.png')}"
        
        if not heatmap_path.exists():
            metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
            if not metadata_path.exists():
                return {"status": "pending", "message": "Waiting for metadata"}
            
            background_tasks.add_task(generate_heatmap_background, video_name)
            return {"status": "processing"}
        
        return {
            "status": "ready",
            "path": f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}"
        }
    except Exception as e:
        logger.error(f"Heatmap error: {str(e)}")
        return {"status": "error", "message": str(e)}

async def generate_heatmap_background(video_name: str):
    """Versión optimizada del generador de heatmap"""
    try:
        metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
        heatmap_path = OUTPUT_VIDEOS_DIR / f"heatmap_{video_name.replace('.mp4', '.png')}"
        
        # Leer metadata
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Obtener frame de fondo
        video_path = VIDEOS_ORIGINAL_DIR / video_name
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise Exception("Cannot open video")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Obtener frame del medio
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, background = cap.read()
        cap.release()

        if not ret:
            raise Exception("Cannot read background frame")

        # Oscurecer fondo
        background = cv2.convertScaleAbs(background, alpha=0.3, beta=0)

        # Crear heatmap
        heatmap_data = np.zeros((height, width), dtype=np.float32)
        
        # Procesar detecciones en lotes
        batch_size = 100
        for i in range(0, len(metadata), batch_size):
            batch = metadata[i:i + batch_size]
            
            for detection in batch:
                for obj in detection.get("objects", []):
                    try:
                        x1, y1, x2, y2 = map(int, obj["coordinates"][0])
                        confidence = float(obj.get("confidence", 1.0))
                        
                        # Validar coordenadas
                        x1 = max(0, min(x1, width-1))
                        x2 = max(0, min(x2, width-1))
                        y1 = max(0, min(y1, height-1))
                        y2 = max(0, min(y2, height-1))
                        
                        if x1 >= x2 or y1 >= y2:
                            continue
                        
                        # Crear máscara gaussiana optimizada
                        center_x = (x1 + x2) // 2
                        center_y = (y1 + y2) // 2
                        sigma = max(x2 - x1, y2 - y1) / 4
                        
                        window_size = int(sigma * 3)
                        y_min = max(0, center_y - window_size)
                        y_max = min(height, center_y + window_size)
                        x_min = max(0, center_x - window_size)
                        x_max = min(width, center_x + window_size)
                        
                        y, x = np.ogrid[y_min-center_y:y_max-center_y, x_min-center_x:x_max-center_x]
                        mask = np.exp(-(x*x + y*y) / (2*sigma*sigma))
                        heatmap_data[y_min:y_max, x_min:x_max] += mask * confidence

                    except Exception as e:
                        print(f"Error in detection: {str(e)}")
                        continue

        if np.max(heatmap_data) > 0:
            # Normalizar y procesar
            heatmap_data = cv2.normalize(heatmap_data, None, 0, 255, cv2.NORM_MINMAX)
            heatmap_data = heatmap_data.astype(np.uint8)
            heatmap_data[heatmap_data < 50] = 0
            heatmap_colored = cv2.applyColorMap(heatmap_data, cv2.COLORMAP_JET)
            
            # Combinar con fondo
            result = cv2.addWeighted(background, 1, heatmap_colored, 0.7, 0)
            
            # Guardar
            cv2.imwrite(str(heatmap_path), result, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            
            # Actualizar base de datos
            heatmap_rel_path = f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}"
            insert_or_update_video_data(video_name, heatmap_path=heatmap_rel_path)
            
            return str(heatmap_path)
        
        raise Exception("No detections found for heatmap generation")

    except Exception as e:
        print(f"Error generating heatmap: {str(e)}")
        if heatmap_path.exists():
            os.remove(str(heatmap_path))
        raise e