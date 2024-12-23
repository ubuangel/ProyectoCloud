from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os
import json
from config import *

metadata_router = APIRouter()

@metadata_router.get("/{video_name}")
def get_metadata(video_name: str):
    """Get metadata for specific video"""
    metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
    
    if not metadata_path.exists():
        return JSONResponse(
            content={"error": "Metadata not found", "status": "not_found"}, 
            status_code=404
        )
        
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        return {"metadata": metadata, "status": "found"}
    except Exception as e:
        return JSONResponse(
            content={"error": str(e), "status": "error"}, 
            status_code=500
        )

@metadata_router.get("/search/{object_label}")
def search_object(object_label: str):
    """Search objects by label and return frames"""
    results = []
    
    try:
        for metadata_file in os.listdir(METADATA_DIR):
            if metadata_file.endswith('.json'):
                with open(os.path.join(METADATA_DIR, metadata_file), "r") as f:
                    metadata = json.load(f)
                
                for detection in metadata:
                    frame_results = []
                    for obj in detection.get("objects", []):
                        if obj["label"].lower() == object_label.lower():
                            frame_results.append({
                                "coordinates": obj["coordinates"],
                                "confidence": obj.get("confidence", 1.0)
                            })
                    
                    if frame_results:
                        results.append({
                            "video": metadata_file.replace('.json', ''),
                            "frame": detection["frame"],
                            "objects": frame_results
                        })
        
        if not results:
            return JSONResponse(
                content={"error": f"No objects found with label '{object_label}'",
                        "status": "not_found"},
                status_code=404
            )
            
        results.sort(key=lambda x: max(obj["confidence"] for obj in x["objects"]), reverse=True)
        return {"results": results, "status": "found"}
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e), "status": "error"},
            status_code=500
        )
    
@metadata_router.get("/objects/{video_name}")
def get_video_objects(video_name: str):
    """Get unique objects detected in a specific video"""
    try:
        metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
        
        if not metadata_path.exists():
            return JSONResponse(
                content={"error": "Metadata not found", "status": "not_found"},
                status_code=404
            )
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            
        # Obtener objetos únicos con sus frames
        unique_objects = {}
        for detection in metadata:
            frame_number = detection["frame"]
            for obj in detection.get("objects", []):
                label = obj["label"]
                if label not in unique_objects:
                    unique_objects[label] = []
                unique_objects[label].append({
                    "frame": frame_number,
                    "confidence": obj["confidence"],
                    "timestamp": frame_number / 30  # Asumiendo 30 FPS
                })
        
        # Convertir a lista ordenada
        objects_list = [
            {"label": label, "occurrences": sorted(frames, key=lambda x: x["frame"])}
            for label, frames in unique_objects.items()
        ]
        
        return {"objects": objects_list, "status": "found"}
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e), "status": "error"},
            status_code=500
        )