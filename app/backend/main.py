from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException
from starlette.types import Scope, Receive, Send
from video_routes import video_router
from metadata_routes import metadata_router
from heatmap import heatmap_router
from database import init_database
from config import *
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sistema de Detección de Videos")

# Inicializar la base de datos al inicio
init_database()

class VideoStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Send, send: Send):
        headers = [
            (b"access-control-allow-origin", b"*"),
            (b"access-control-allow-methods", b"GET, HEAD, OPTIONS"),
            (b"access-control-allow-headers", b"range, accept-ranges, content-type"),
            (b"access-control-expose-headers", b"content-range, content-length, accept-ranges"),
            (b"accept-ranges", b"bytes"),
        ]
        
        if scope["type"] == "http":
            path = scope["path"]
            if path.endswith((".mp4", ".webm")):
                new_headers = list(scope["headers"])
                new_headers.extend(headers)
                scope["headers"] = new_headers
        
        await super().__call__(scope, receive, send)

# Actualizar el montaje de los directorios estáticos
app.mount("/videos_original", VideoStaticFiles(directory=str(VIDEOS_ORIGINAL_DIR)), name="videos_original")
app.mount("/output_videos", VideoStaticFiles(directory=str(OUTPUT_VIDEOS_DIR)), name="output_videos")

# Montar los archivos estáticos del frontend correctamente
frontend_dir = BASE_DIR.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(video_router, prefix="/videos", tags=["Videos"])
app.include_router(metadata_router, prefix="/metadata", tags=["Metadata"])
app.include_router(heatmap_router, prefix="/heatmap", tags=["Heatmap"])

# Servir archivos estáticos individuales
@app.get("/")
async def read_root():
    return FileResponse(str(frontend_dir / "index.html"))

@app.get("/favicon.ico")
async def get_favicon():
    favicon_path = frontend_dir / "favicon.ico"
    if not favicon_path.exists():
        # Si no existe el favicon, retornar una respuesta vacía
        return JSONResponse(content={})
    return FileResponse(str(favicon_path))

@app.get("/style.css")
async def get_css():
    return FileResponse(str(frontend_dir / "style.css"))

@app.get("/script.js")
async def get_js():
    return FileResponse(str(frontend_dir / "script.js"))

# Manejar errores 404
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    if request.url.path.startswith("/static/"):
        return FileResponse(str(frontend_dir / "index.html"))
    return JSONResponse(
        status_code=404,
        content={"detail": "Not Found"}
    )

# Manejar errores de tipo
@app.exception_handler(TypeError)
async def type_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

@app.on_event("startup")
async def startup_event():
    print(f"Aplicación iniciada en {API_HOST}:{API_PORT}")