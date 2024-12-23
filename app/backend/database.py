import sqlite3
import os
from config import *
import logging
import time

logger = logging.getLogger(__name__)

def init_database():
    """Inicializar la base de datos si no existe"""
    if not DATABASE_PATH.exists():
        create_database()
    else:
        # Verificar y actualizar registros existentes
        sync_database_with_files()

def sync_database_with_files():
    """Sincronizar la base de datos con los archivos existentes"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    # Buscar archivos procesados y heatmaps existentes
    for video_file in VIDEOS_ORIGINAL_DIR.glob('*.mp4'):
        video_name = video_file.name
        processed_path = OUTPUT_VIDEOS_DIR / f"processed_{video_name}"
        heatmap_path = OUTPUT_VIDEOS_DIR / f"heatmap_{video_name.replace('.mp4', '.png')}"
        metadata_path = METADATA_DIR / f"{video_name.replace('.mp4', '.json')}"
        
        if processed_path.exists() or heatmap_path.exists():
            # Construir rutas relativas
            processed_rel_path = f"/output_videos/processed_{video_name}" if processed_path.exists() else ""
            heatmap_rel_path = f"/output_videos/heatmap_{video_name.replace('.mp4', '.png')}" if heatmap_path.exists() else ""
            
            # Leer metadata si existe
            metadata_json = ""
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata_json = f.read()
            
            # Actualizar o insertar en la base de datos
            insert_or_update_video_data(
                video_name,
                metadata=metadata_json,
                processed_video_path=processed_rel_path,
                heatmap_path=heatmap_rel_path
            )
    
    conn.close()

def create_database():
    """Crear base de datos SQLite para metadata y archivos procesados"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    # Tabla para metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_name TEXT NOT NULL UNIQUE,
            metadata TEXT NOT NULL,
            processed_video_path TEXT,
            heatmap_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def insert_or_update_video_data(video_name, metadata=None, processed_video_path=None, heatmap_path=None):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = sqlite3.connect(str(DATABASE_PATH))
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM metadata WHERE video_name = ?", (video_name,))
            existing = cursor.fetchone()
            
            if existing:
                update_fields = []
                update_values = []
                
                if metadata is not None:
                    update_fields.append("metadata = ?")
                    update_values.append(metadata)
                
                if processed_video_path is not None:
                    update_fields.append("processed_video_path = ?")
                    update_values.append(processed_video_path)
                
                if heatmap_path is not None:
                    update_fields.append("heatmap_path = ?")
                    update_values.append(heatmap_path)
                
                if update_fields:
                    query = f"""
                        UPDATE metadata 
                        SET {', '.join(update_fields)}
                        WHERE video_name = ?
                    """
                    cursor.execute(query, tuple(update_values + [video_name]))
            else:
                cursor.execute("""
                    INSERT INTO metadata (video_name, metadata, processed_video_path, heatmap_path)
                    VALUES (?, ?, ?, ?)
                """, (video_name, metadata or "", processed_video_path or "", heatmap_path or ""))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            retry_count += 1
            if retry_count == max_retries:
                logger.error(f"Database error after {max_retries} retries: {str(e)}")
                return False
            time.sleep(1)

def get_video_data(video_name):
    """Obtener toda la información de un video específico"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT video_name, metadata, processed_video_path, heatmap_path, created_at
        FROM metadata 
        WHERE video_name = ?
    """, (video_name,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "video_name": result[0],
            "metadata": result[1],
            "processed_video_path": result[2],
            "heatmap_path": result[3],
            "created_at": result[4]
        }
    return None

def check_video_paths(video_name):
    """Función de debug para verificar las rutas en la base de datos"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT processed_video_path, heatmap_path
        FROM metadata 
        WHERE video_name = ?
    """, (video_name,))
    
    result = cursor.fetchone()
    conn.close()
    
    print(f"Rutas en DB para {video_name}:")
    print(f"Video procesado: {result[0] if result else 'No encontrado'}")
    print(f"Heatmap: {result[1] if result else 'No encontrado'}")
    
    return result