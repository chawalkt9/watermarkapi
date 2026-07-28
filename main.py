import io
import requests
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

app = FastAPI(
    title="Image Watermark API",
    description="Add dynamic text strip at the bottom of an image.",
    version="2.0.0"
)

def process_watermark(base_image_bytes: bytes, watermark_text: str) -> io.BytesIO:
    base_img = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")
    width, height = base_img.size

    # BOTTOM STRIP SETUP
    strip_height = int(height * 0.08) 
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Draw semi-transparent black background strip
    draw.rectangle(
        [(0, height - strip_height), (width, height)],
        fill=(0, 0, 0, 200)
    )

    # Dynamic Font Size Calculation
    font_size = int(strip_height * 0.70)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.load_default(size=font_size)
        except TypeError:
            font = ImageFont.load_default()

    # Calculate text placement
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = (width - text_w) // 2
    text_y = (height - strip_height) + (strip_height - text_h) // 2 - bbox[1]

    # Draw Text
    draw.text((text_x, text_y), watermark_text, fill=(255, 255, 255, 255), font=font)

    # Merge layers
    base_img = Image.alpha_composite(base_img, overlay)

    output_io = io.BytesIO()
    base_img.convert("RGB").save(output_io, format="JPEG", quality=95)
    output_io.seek(0)
    return output_io

# Root Route
@app.get("/")
def home():
    return {
        "status": "API is online",
        "usage": "/watermark?url=YOUR_IMAGE_URL&text=YOUR_TEXT"
    }

# Watermark Endpoint
@app.get("/watermark")
async def watermark_image(
    url: str = Query(..., description="Direct URL of the image"),
    text: str = Query("Join @kt_deals", description="Text to render on the bottom strip")
):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Unable to fetch image from given URL")

        # Process image with dynamic text
        processed_io = process_watermark(resp.content, text)

        return StreamingResponse(processed_io, media_type="image/jpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
