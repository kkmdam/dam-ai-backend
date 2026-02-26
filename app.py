from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os

app = Flask(__name__)
CORS(app) # Allows your HTML to talk to this Python file

# The server will hold these keys securely
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
WEATHER_KEY = os.environ.get("WEATHER_API_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_kakkayam_weather():
    """Fetches the 24-hour rainfall forecast for Kakkayam Dam."""
    lat, lon = "11.54", "75.92"
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
    try:
        response = requests.get(url).json()
        rain_total = 0
        # Check the next 8 periods (which covers 24 hours, as each is 3 hours)
        for item in response.get('list', [])[:8]:
            if 'rain' in item and '3h' in item['rain']:
                rain_total += item['rain']['3h']
        return f"Expected rainfall in next 24hrs: {round(rain_total, 1)} mm."
    except Exception as e:
        return "Weather data currently unavailable."

@app.route('/api/generate-advisory', methods=['POST'])
def generate_advisory():
    data = request.json
    
    # 1. Get the live weather
    weather_forecast = get_kakkayam_weather()
    
    # 2. Tell the AI what is happening
    prompt = f"""
    You are the Chief Engineer AI for Kakkayam Dam. 
    Current Dam Status:
    - Current WL: {data.get('wlCur')}m, Target WL: {data.get('wlTar')}m.
    - Timeframe: {data.get('hours')} hours.
    - Planned Spillway Discharge: {data.get('qSpill')} cumecs.
    - Weather Forecast for Catchment: {weather_forecast}
    
    Write a short, professional "Risk & Weather Analysis" for the operators. 
    If the planned discharge is high AND heavy rain is expected, warn them. 
    Then, write a short official WhatsApp advisory for the District Collector.
    """
    
    # 3. Get the AI's answer and send it back to the HTML
    response = model.generate_content(prompt)
    return jsonify({"status": "success", "advisory": response.text, "weather": weather_forecast})

# This line starts the server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)