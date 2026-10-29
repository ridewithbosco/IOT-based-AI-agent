from tools import get_navigation_instructions
from dotenv import load_dotenv
import os

load_dotenv()

print("API Key present:", bool(os.getenv("GOOGLE_MAPS_API_KEY")))
print("Calling tool directly...")
result = get_navigation_instructions("Navigate me to techno main saltlake")
print("Tool Result:")
print(result)
