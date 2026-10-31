import os 
from dotenv import load_dotenv 
from google import genai 
load_dotenv() 
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY')) 
r = client.models.generate_content(model='gemini-2.0-flash-001', contents='Say hello in one word') 
print('Gemini OK:', r.text) 
