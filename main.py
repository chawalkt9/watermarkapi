import io
import re
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont
from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.responses import StreamingResponse

app = FastAPI(
    title="Image Watermark API",
    description="Pass image URL in query param to overlay circular logo & bottom strip watermark.",
    version="1.0.0"
)

# --- CONFIGURATION ---
TOP_LOGO_URL = "https://cdn5.telesco.pe/file/aSf192hYDvLjeIu3QeKrEm5d5xwzUYN5wKLLNfbvOpuz6PKzQPyZ4up71rfuxRSwujzDh-AsMI4xOSplp2HjZ7lsn9-s4L-99jJG7VlKtqcG_62mytf04QZet_QoVVWlxYscNDhofqiPec2HCXUsc7DSV0c8BBLA2muRkN6IGhA9XZhjrYJqLGbLH9HFaQwImozgwXi-lBD_89f8XoiqIMS9KZaW8udXb-aEPaBgFk_sRHPr_joYXxJnXlo1pJSV8dAQuEzoxfBTR1eppST0l-BpNTDeJaPyWslYguzSIC3rr5ePrqlQ3Yldmkc0uXQhe_68AlZ6Jzdwfku0UTrbZw.jpg"
CACHED_TOP_LOGO = None

def get_circular_logo(url: str) -> Image.Image:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        logo_img = Image.open(io.BytesIO(response.content)).convert("RGBA")
        size = (min(logo_img.size), min(logo_img.size))
        logo_img = logo_img.resize(size, Image.Resampling.LANCZOS)
        
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        
        output = ImageOps.fit(logo_img, size, centering=(0.5, 0.5))
        output.putalpha(mask)
        return output
    except Exception as e:
        print(f"Failed to fetch logo: {e}")
        return Image.new("RGBA", (100, 100), (0, 0, 0, 0))

def get_top_logo() -> Image.Image:
    global CACHED_TOP_LOGO
    if CACHED_TOP_LOGO is None:
        CACHED_TOP_LOGO = get_circular_logo(TOP_LOGO_URL)
    return CACHED_TOP_LOGO.copy()

def process_watermark(base_image_bytes: bytes) -> io.BytesIO:
    base_img = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")
    width, height = base_img.size

    # 1. TOP-LEFT LOGO
    top_logo = get_top_logo()
    top_w = int(width * 0.12)
    top_logo = top_logo.resize((top_w, top_w), Image.Resampling.LANCZOS)
    margin = int(width * 0.03)
    base_img.paste(top_logo, (margin, margin), top_logo)

    # 2. BOTTOM STRIP
    strip_height = int(height * 0.08) 
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    draw.rectangle(
        [(0, height - strip_height), (width, height)],
        fill=(0, 0, 0, 200)
    )

    text = "Join @kt_deals"
    font_size = int(strip_height * 0.70)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = (width - text_w) // 2
    text_y = (height - strip_height) + (strip_height - text_h) // 2 - bbox[1]

    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)

    base_img = Image.alpha_composite(base_img, overlay)

    output_io = io.BytesIO()
    base_img.convert("RGB").save(output_io, format="JPEG", quality=95)
    output_io.seek(0)
    return output_io

# Root Route (Healthcheck)
@app.get("/")
def home():
    return {"status": "API is online", "endpoint": "/watermark?url=YOUR_IMAGE_URL"}

# Watermark API Endpoint
@app.get("/watermark")
async def watermark_image(url: str = Query(..., description="Direct URL of the image to add watermark")):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Unable to fetch image from given URL")

        # Process image
        processed_io = process_watermark(resp.content)

        # Return photo directly as image/jpeg stream
        return StreamingResponse(processed_io, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
