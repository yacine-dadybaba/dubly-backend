from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import requests
import re
from bs4 import BeautifulSoup

app = FastAPI(title="DUBLY Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

def extract_price_from_url(url):
    """Extrait le prix en EURO depuis une page Temu/AliExpress"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.fr/',
        }
        
        # Forcer l'EUR dans l'URL
        if 'temu.com' in url or 'aliexpress.com' in url:
            if '?' in url:
                forced_url = url + '&currency=EUR'
            else:
                forced_url = url + '?currency=EUR'
        else:
            forced_url = url
            
        print(f"🔍 Tentative d'extraction du prix depuis: {forced_url}")
        response = requests.get(forced_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pour Temu
        if 'temu.com' in url:
            # Chercher le symbole €
            price_element = soup.find(string=re.compile(r'€\s*[\d,\.]+|[\d,\.]+\s*€'))
            if price_element:
                price_text = re.search(r'[\d,\.]+', price_element)
                if price_text:
                    return float(price_text.group().replace(',', '.'))
            
            # Chercher dans les meta
            price_meta = soup.find('meta', {'property': 'product:price:amount'})
            if price_meta:
                return float(price_meta['content'])
        
        # Pour AliExpress
        elif 'aliexpress.com' in url:
            price_span = soup.find('span', class_='product-price-value')
            if not price_span:
                price_span = soup.find('span', {'itemprop': 'price'})
            if price_span:
                price_text = re.search(r'[\d,\.]+', price_span.text)
                if price_text:
                    return float(price_text.group().replace(',', '.'))
        
        print("❌ Prix non trouvé")
        return None
    except Exception as e:
        print(f"❌ Erreur extraction prix: {e}")
        return None

@app.get("/")
async def root():
    return {"message": "DUBLY Backend is running! 🎙️"}

@app.post("/video/price")
async def get_product_price(request: VideoRequest):
    """Extrait le prix d'un produit Temu/AliExpress en EURO"""
    try:
        price = extract_price_from_url(request.url)
        if price:
            return {"success": True, "price": price, "currency": "EUR"}
        else:
            return {"success": False, "message": "Prix non trouvé. Vérifiez manuellement."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur: {str(e)}")

@app.post("/video/info")
async def get_video_info(request: VideoRequest):
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
    try:
        video_id = str(uuid.uuid4())[:8]
        output_path = f"downloads/{video_id}"
        
        ydl_opts = {
            'outtmpl': f'{output_path}.%(ext)s',
            'format': 'worst[height<=360]',
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
                "download_url": f"https://dubly-backend.onrender.com/video/file/{os.path.basename(filename)}"
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur de téléchargement: {str(e)}")

@app.get("/video/file/{filename}")
async def get_video_file(filename: str):
    file_path = f"downloads/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="video/mp4", filename=filename)
    else:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "DUBLY Backend"}

os.makedirs("downloads", exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)