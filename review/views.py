import os
import json
import requests
import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from selenium import webdriver
from review.convertor import cloudinary_to_base64

# Load Cloudinary configuration from environment variables
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def take_screenshot(url):
    """Takes a screenshot of the given URL, uploads it to Cloudinary,
       and converts the image URL to a base64 string."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        browser = webdriver.Chrome(options=options)
        browser.get(url)
        total_height = browser.execute_script("return document.body.parentNode.scrollHeight")
        browser.set_window_size(1200, total_height)
        screenshot = browser.get_screenshot_as_png()
    except Exception as e:
        return {"error": f"Failed to capture screenshot: {str(e)}"}
    finally:
        browser.quit()

    try:
        # Upload screenshot to Cloudinary
        upload_response = cloudinary.uploader.upload(
            screenshot,
            folder="screenshots",
            resource_type="image"
        )
        cloudinary_url = upload_response.get("secure_url")  # Ensure using secure URL
    except Exception as e:
        return {"error": f"Cloudinary upload failed: {str(e)}"}

    # Convert Cloudinary image URL to a base64 string for Gemini processing
    base64_image = cloudinary_to_base64(cloudinary_url)

    return {
        "cloudinary_url": cloudinary_url,
        "base64_image": base64_image
    }

def send_to_gemini(base64_image):
    """Sends the base64 image to the Gemini API and returns its JSON response."""
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    API_KEY = os.getenv("GEMINI_API_KEY")

    if not API_KEY:
        return {"error": "Gemini API key is missing from environment variables."}

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemini-1.5-pro",
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64_image
                        }
                    },
                    {
                        "text": (
                            "Take a good look at the image; it is a full screenshot of a portfolio website. "
                            "Analyze the image I have provided and give me a full detailed review of the portfolio website. "
                            "Highlight the good aspects, areas for improvement, and necessary changes."
                        )
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(f"{API_URL}?key={API_KEY}", headers=headers, json=payload)
        response_data = response.json()

        if response.status_code != 200:
            return {"error": f"API request failed with status {response.status_code}: {response_data}"}

        return response_data

    except requests.exceptions.RequestException as e:
        return {"error": f"Request to Gemini API failed: {str(e)}"}

@require_http_methods(["POST"])
def submit_url(request):
    try:
        data = json.loads(request.body)
        domain = data.get("domain")

        if not domain:
            return JsonResponse({"error": "No domain provided."}, status=400)

        # Capture screenshot
        screenshot_data = take_screenshot(domain)
        if "error" in screenshot_data:
            return JsonResponse({"error": screenshot_data["error"]}, status=400)

        # Send screenshot to Gemini API
        gemini_response = send_to_gemini(screenshot_data["base64_image"])

        if "error" in gemini_response:
            return JsonResponse({"error": gemini_response["error"]}, status=503)

        # Extract review text safely
        try:
            review_text = gemini_response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return JsonResponse({"error": "Unable to extract review text from Gemini API response."}, status=500)

        # Return screenshot URL and review
        return JsonResponse({
            "screenshot_url": screenshot_data["cloudinary_url"],
            "review": review_text
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

def index(request):
    """Render the main index page."""
    return render(request, "index.html")
