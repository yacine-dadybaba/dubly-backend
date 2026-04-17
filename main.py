from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import subprocess

app = FastAPI(title="DUBLY Backend")

# Autoriser les requêtes depuis Flutter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

class VideoInfo(BaseModel):
    title: str
    duration: int
    thumbnail: str
    url: str
    download_url: str

@app.get("/")
async def root():
    return {"message": "DUBLY Backend is running! 🎙️"}

@app.post("/video/info")
async def get_video_info(request: VideoRequest):
    """Récupère les informations d'une vidéo sans la télécharger"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            
            return {
                "title": info.get('title', 'Vidéo sans titre'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "url": request.url,
                "download_url": info.get('url', '')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur: {str(e)}")

@app.post("/video/download")
async def download_video(request: VideoRequest):
    """Télécharge une vidéo et retourne le chemin"""
    try:
        # Créer un nom de fichier unique
        video_id = str(uuid.uuid4())[:8]
        output_path = f"downloads/{video_id}"
        
        ydl_opts = {
            'outtmpl': f'{output_path}.%(ext)s',
            'format': 'best[height<=720]',  # Limiter à 720p pour la rapidité
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=True)
            filename = ydl.prepare_filename(info)
            
            return {
                "success": True,
                "filename": filename,
                "title": info.get('title', 'Vidéo sans titre'),
                "duration": info.get('duration', 0),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de téléchargement: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "DUBLY Backend"}

# Créer le dossier downloads s'il n'existe pas
os.makedirs("downloads", exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)