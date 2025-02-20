import base64
import requests
from io import BytesIO
from PIL import Image

def cloudinary_to_base64(url, max_width=800, max_height=800, quality=50):
    # Fetch the image from Cloudinary
    response = requests.get(url)
    if response.status_code == 200:
        image_data = response.content
        image = Image.open(BytesIO(image_data))
        
        # Resize the image to fit within the max_width and max_height
        image.thumbnail((max_width, max_height))

        # Compress the image by reducing quality (JPEG format is used for compression)
        buffered = BytesIO()
        image.save(buffered, format="JPEG", quality=quality)

        # Convert the compressed image to base64
        base64_encoded = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return base64_encoded
    else:
        return "Failed to fetch image"




