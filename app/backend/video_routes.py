from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
import os
import json
import cv2
from config import *
from database import insert_or_update_video_data, get_video_data
from ultralytics import YOLO
import numpy as np
import subprocess
from heatmap import generate_heatmap_background
import random
import asyncio
import logging

logger = logging.getLogger(__name__)
video_router = APIRouter()

class ProcessingStatus:
    def __init__(self):
        self.status = {}
        self._lock = asyncio.Lock()

    async def set_progress(self, video_name: str, progress: int, step: str):
        async with self._lock:
            self.status[video_name] = {
                "status": "processing" if progress < 100 else "completed",
                "progress": progress,
                "step": step,
                "files": await self.check_generated_files(video_name)
            }

    async def get_progress(self, video_name: str):
        async with self._lock:
            if video_name not in self.status:
                return {
                    "status": "not_started",
                    "progress": 0,
                    "step": "not_started",
                    "files": await self.check_generated_files(video_name)
                }
            return self.status[video_name]

    async def check_generated_files(self, video_name: str):
        metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
        processed_path = OUTPUT_VIDEOS_DIR / f"processed_{video_name}"
        heatmap_path = OUTPUT_VIDEOS_DIR / f"heatmap_{video_name.replace('.mp4', '.png')}"
        
        return {
            "metadata_ready": metadata_path.exists() and metadata_path.stat().st_size > 0,
            "video_ready": processed_path.exists() and processed_path.stat().st_size > 0,
            "heatmap_ready": heatmap_path.exists() and heatmap_path.stat().st_size > 0
        }

    def clear_progress(self, video_name: str):
        if video_name in self.status:
            del self.status[video_name]

processing_status = ProcessingStatus()

@video_router.get("/available-videos")
async def get_available_videos():
    try:
        if not LIST_FILE.exists():
            return {"videos": [], "message": "No se encontró el archivo de lista"}
        
        with open(LIST_FILE, "r") as file:
            videos = [
                line.strip() + ".mp4"
                for line in file.readlines()
                if line.strip() and 
                (VIDEOS_ORIGINAL_DIR / f"{line.strip()}.mp4").exists()
            ]
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Error en available-videos: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "videos": [],
                "error": str(e),
                "detail": "Error al obtener la lista de videos"
            }
        )

@video_router.get("/process/{video_name}")
async def process_video(video_name: str, background_tasks: BackgroundTasks):
    try:
        video_path = VIDEOS_ORIGINAL_DIR / video_name
        if not video_path.exists():
            raise HTTPException(status_code=404, detail=f"Video no encontrado")

        # Verificar si ya está en proceso
        current_status = await processing_status.get_progress(video_name)
        if current_status["status"] == "processing":
            return current_status

        # Verificar si ya está todo procesado
        files_status = current_status.get("files", {})
        if (files_status.get("metadata_ready", False) and 
            files_status.get("video_ready", False) and 
            files_status.get("heatmap_ready", False)):
            
            return {
                "status": "completed",
                "progress": 100,
                "step": "completed",
                "processed_video_path": f"/output_videos/processed_{video_name}",
                "heatmap_path": f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}"
            }

        # Iniciar procesamiento
        background_tasks.add_task(
            process_video_background,
            video_name
        )

        return {
            "status": "processing",
            "progress": 0,
            "step": "starting"
        }

    except Exception as e:
        logger.error(f"Error en process_video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@video_router.get("/status/{video_name}")
async def get_processing_status(video_name: str):
    try:
        current_status = await processing_status.get_progress(video_name)
        files_status = current_status.get("files", {})

        # Si todos los archivos existen, el proceso está completo
        if (files_status.get("metadata_ready") and 
            files_status.get("video_ready") and 
            files_status.get("heatmap_ready")):
            
            return {
                "status": "completed",
                "progress": 100,
                "step": "completed",
                "processed_video_path": f"/output_videos/processed_{video_name}",
                "heatmap_path": f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}"
            }

        return current_status
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return {"status": "error", "message": str(e)}

async def process_video_background(video_name: str):
    try:
        video_path = VIDEOS_ORIGINAL_DIR / video_name
        metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
        output_path = OUTPUT_VIDEOS_DIR / f"processed_{video_name}"

        # Verificar archivos existentes
        files_status = await processing_status.check_generated_files(video_name)

        # Generar metadata si no existe
        if not files_status["metadata_ready"]:
            await processing_status.set_progress(video_name, 0, "generating_metadata")
            metadata = generate_metadata(str(video_path), str(metadata_path))
            metadata_json = json.dumps(metadata)
            insert_or_update_video_data(video_name, metadata=metadata_json)
            await processing_status.set_progress(video_name, 33, "metadata_complete")

        # Procesar video si no existe
        if not files_status["video_ready"]:
            await processing_status.set_progress(video_name, 33, "processing_video")
            with open(metadata_path) as f:
                metadata = json.load(f)
            
            await process_video_with_metadata(video_path, output_path, metadata)
            processed_path = f"/output_videos/processed_{video_name}"
            insert_or_update_video_data(video_name, processed_video_path=processed_path)
            await processing_status.set_progress(video_name, 66, "video_complete")

        # Generar heatmap si no existe
        if not files_status["heatmap_ready"]:
            await processing_status.set_progress(video_name, 66, "generating_heatmap")
            await generate_heatmap_background(video_name)

        # Verificar estado final
        final_status = await processing_status.check_generated_files(video_name)
        if all(final_status.values()):
            await processing_status.set_progress(video_name, 100, "completed")
        else:
            raise Exception("No se generaron todos los archivos correctamente")

    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
        await processing_status.set_progress(video_name, -1, f"error: {str(e)}")
        raise

@video_router.get("/{video_name}")
async def serve_video(video_name: str):
    try:
        status = await processing_status.get_progress(video_name)
        files_status = status.get("files", {})
        
        if status["status"] == "completed" and all(files_status.values()):
            return {
                "path": f"/output_videos/processed_{video_name}",
                "heatmap_path": f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}",
                "processed": True,
                "status": "ready"
            }
        
        return {
            "path": f"/videos_original/{video_name}",
            "processed": False,
            "status": "needs_processing"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def check_video_status(video_name: str):
    processed_path = OUTPUT_VIDEOS_DIR / f"processed_{video_name}"
    metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
    original_path = VIDEOS_ORIGINAL_DIR / video_name
    
    return {
        "has_processed": processed_path.exists(),
        "has_metadata": metadata_path.exists(),
        "has_original": original_path.exists()
    }

def generate_metadata(video_path: str, output_metadata_path: str):
    model = YOLO(str(MODEL_PATH))
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise Exception("Could not open video")

    metadata = []
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        detections = []

        for r in results[0]:
            for box, cls, conf in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf):
                if conf > 0.3:
                    coords = box.cpu().numpy()
                    detections.append({
                        "label": model.names[int(cls)],
                        "confidence": float(conf),
                        "coordinates": [[int(c) for c in coords]]
                    })

        if detections:
            metadata.append({
                "frame": frame_count,
                "objects": detections
            })

        frame_count += 1

    cap.release()
    
    with open(output_metadata_path, 'w') as f:
        json.dump(metadata, f)

    return metadata

async def process_video_with_metadata(input_path, output_path, metadata):
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise Exception("Could not open video for processing")

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_output = str(output_path).replace('.mp4', '_temp.mp4')
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

    if not writer.isOpened():
        raise Exception("No se pudo inicializar el writer de video")

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_metadata = next((m for m in metadata if m["frame"] == frame_count), None)
            
            if frame_metadata:
                for obj in frame_metadata["objects"]:
                    try:
                        x1, y1, x2, y2 = map(int, obj["coordinates"][0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{obj['label']} {obj['confidence']:.2f}",
                                 (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    except (ValueError, IndexError) as e:
                        logger.error(f"Error dibujando detección: {str(e)}")
                        continue

            writer.write(frame)
            frame_count += 1

    finally:
        cap.release()
        writer.release()

    try:
        subprocess.run([
            'ffmpeg', '-i', temp_output,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            str(output_path)
        ], check=True)
        
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error en la conversión de video: {str(e)}")
    except Exception as e:
        raise Exception(f"Error inesperado: {str(e)}")

    if not os.path.exists(str(output_path)):
        raise Exception("El archivo de video no se generó")
        
    if os.path.getsize(str(output_path)) == 0:
        os.remove(str(output_path))
        raise Exception("El archivo de video generado está vacío")

    return str(output_path)

@video_router.get("/rtsp/stream/{video_name}")
async def stream_frame(video_name: str):
    try:
        video_path = VIDEOS_ORIGINAL_DIR / video_name
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video no encontrado")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="No se pudo abrir el video")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        random_frame = random.randint(0, total_frames-1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame)
        
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(status_code=500, detail="Error leyendo frame")

        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        return Response(
            content=frame_bytes,
            media_type="image/jpeg"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))