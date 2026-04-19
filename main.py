from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json
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
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        print(f"🔍 Tentative d'extraction du prix depuis: {url}")
        
        if 'order_checkout' in url or 'bgad_order' in url:
            print("⚠️ Lien de checkout détecté, extraction impossible")
            return None
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        print(f"📄 URL finale: {response.url}")
        print(f"📄 Statut HTTP: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Méthode 1 : Chercher dans les scripts JSON-LD
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'offers' in data:
                        price = data['offers'].get('price')
                        if price:
                            print(f"✅ Prix trouvé via JSON-LD: {price}")
                            return float(price)
            except:
                pass
        
        # Méthode 2 : Chercher dans les meta tags
        price_selectors = [
            {'property': 'product:price:amount'},
            {'property': 'og:price:amount'},
            {'name': 'twitter:data1'},
            {'itemprop': 'price'},
        ]
        
        for selector in price_selectors:
            meta = soup.find('meta', selector)
            if meta and meta.get('content'):
                try:
                    price = float(meta['content'])
                    print(f"✅ Prix trouvé via meta: {price}")
                    return price
                except:
                    pass
        
        # Méthode 3 : Chercher avec regex
        prices = re.findall(r'€\s*(\d+[.,]?\d*)', response.text)
        if prices:
            print(f"💰 Prix trouvés dans le HTML: {prices[:5]}")
            for p in prices[:5]:
                try:
                    return float(p.replace(',', '.'))
                except:
                    pass
        
        prices2 = re.findall(r'(\d+[.,]?\d*)\s*€', response.text)
        if prices2:
            print(f"💰 Prix trouvés (motif 2): {prices2[:5]}")
            for p in prices2[:5]:
                try:
                    return float(p.replace(',', '.'))
                except:
                    pass
        
        print("❌ Aucun prix trouvé")
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