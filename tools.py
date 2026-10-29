import cv2
import base64
import requests
import os
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def capture_image() -> str:
    """Capture one frame from the PiCamera, resize it, encodes it as Base64 JPEG (raw string) and returns it"""
    
    # Try fetching from the running EnvironmentScanner first to avoid camera lock errors
    try:
        from cam import env_scanner
        if getattr(env_scanner, "_running", False):
            import time
            attempts = 0
            # Wait up to 10 seconds for YOLO to initialize and capture the first frame
            while getattr(env_scanner, "latest_frame", None) is None and attempts < 20:
                time.sleep(0.5)
                attempts += 1
                
            if getattr(env_scanner, "latest_frame", None) is not None:
                frame_b64 = env_scanner.get_latest_frame_b64()
                if frame_b64:
                    return frame_b64
                    
            # If we reach here, the scanner holds the camera but can't get a frame
            raise RuntimeError("Camera is locked by scanner, but returning empty frames. Is it plugged in?")
            
    except ImportError:
        pass # env_scanner not available, fallback is safe

    # FALLBACK: ONLY reach here if EnvironmentScanner is NOT running!
    cam_urls = [0]
    for idx in cam_urls:
        cap=cv2.VideoCapture(idx)
        if cap.isOpened():
            for _ in range(10):
                cap.read()
            ret, frame = cap.read()
            cap.release()
            if not ret:
                 continue
            cv2.imwrite("image.jpg", frame)
            ref, buf = cv2.imencode(".jpg", frame)
            if ret:
                return base64.b64encode(buf).decode("utf-8")
    raise RuntimeError(f"No PiCamera found (tried {cam_urls})")

def analyze_image_with_query(query: str) -> str:
    """
    Expects a string with 'query'.
    Captures the image and sends the query and the image to
    to Groq's vision chat API and returns the analysis.
    """
    img_b64 = capture_image()
    # Use a valid Groq vision model
    model = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    if not query or not img_b64:
        return "Error: both 'query' and 'image' fields required."

    client=Groq()  
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": query
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                    },
                },
            ],
        }]
    chat_completion=client.chat.completions.create(
        messages=messages,
        model=model
    )

    return chat_completion.choices[0].message.content

# query = "What do u understand from this image?"
# print(analyze_image_with_query(query))

def get_current_gps():
    """
    Replace this mock with actual GPS module readings (e.g., NEO-6M / NEO-8M).
    Should return (latitude, longitude).
    """
    # Example static location — replace with live GPS code.
    return (22.5726, 88.3639)  # Kolkata central coordinates

def extract_destination(query: str) -> str:
    """ Extract destination from user query using a simple regex-based heuristic. 
    For example: "Navigate me to the airport" -> "airport" "How do I go to the railway station?" -> "railway station" 
    """ 
    pattern = r"(?:to|towards|into)\s+(.*)" 
    match = re.search(pattern, query, re.IGNORECASE) 
    if match: 
        return match.group(1).strip() 
    return query # fallback

def get_navigation_instructions(query: str) -> str:
    """
    Provides navigation steps using the Google Maps Directions API.

    Input:
        query (str): A natural language navigation request such as
                     "Navigate me to the railway station".

    Output:
        str: A formatted list of navigation steps with distances
             and geographic coordinates.
    """
    if not GOOGLE_MAPS_API_KEY:
        return "Error: Google Maps API key not found."

    destination = extract_destination(query)
    if not destination:
        return "I couldn't understand the destination."

    lat, lon = get_current_gps()

    url = (
        f"https://maps.googleapis.com/maps/api/directions/json?"
        f"origin={lat},{lon}&destination={destination}&mode=walking&key={GOOGLE_MAPS_API_KEY}"
    )

    response = requests.get(url).json()

    if response.get("status") != "OK":
        return f"Navigation error: {response.get('status')}"

    steps = response["routes"][0]["legs"][0]["steps"]

    instruction_text = f"Navigation steps to {destination}:\n\n"

    for idx, step in enumerate(steps, start=1):
        instruction = re.sub("<.*?>", "", step["html_instructions"])
        distance = step["distance"]["text"]

        start = step["start_location"]
        end = step["end_location"]

        instruction_text += (
            f"{idx}. {instruction} ({distance})\n"
            f"   Start: ({start['lat']}, {start['lng']})\n"
            f"   End:   ({end['lat']}, {end['lng']})\n\n"
        )

    return instruction_text.strip()

