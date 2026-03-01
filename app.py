from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os
import json

app = Flask(__name__)
# This allows browsers to talk to this server
CORS(app)

# The server will hold these keys securely
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
WEATHER_KEY = os.environ.get("WEATHER_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-pro')

def get_kakkayam_weather():
    """Fetches the 24-hour rainfall forecast for Kakkayam Dam."""
    lat, lon = "11.54", "75.92"
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
    try:
        response = requests.get(url).json()
        rain_total = 0
        for item in response.get('list', [])[:8]:
            if 'rain' in item and '3h' in item['rain']:
                rain_total += item['rain']['3h']
        return f"Expected rainfall in next 24hrs: {round(rain_total, 1)} mm."
    except Exception as e:
        return "Weather data currently unavailable."

# NOTE: We added 'OPTIONS' here to answer the browser's security check!
@app.route('/api/parse-plan', methods=['POST', 'OPTIONS'])
def parse_plan():
    # Warmly answer the browser's test knock
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.json
    user_message = data.get('message', '')
    
    prompt = f"""
    You are an AI assistant for a dam control room. Extract the following parameters from the user's message and return ONLY a strict JSON object. If a value is not mentioned, use null.
    User Message: "{user_message}"
    
    Expected JSON format:
    {{
      "target_wl": float (the target water level in meters),
      "time_hours": float (how many hours to evacuate),
      "inflow": float (inflow in cumecs),
      "powerhouse": float (powerhouse discharge in cumecs)
    }}
    """
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        parsed_data = json.loads(clean_json)
        return jsonify({"status": "success", "data": parsed_data})
    except Exception as e:
        return jsonify({"status": "error", "message": "Could not parse parameters."}), 400

# NOTE: We added 'OPTIONS' here too!
@app.route('/api/generate-advisory', methods=['POST', 'OPTIONS'])
def generate_advisory():
    # Warmly answer the browser's test knock
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.json
    weather_forecast = get_kakkayam_weather()
    
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
    try:
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "advisory": response.text, "weather": weather_forecast})
    except Exception as e:
        return jsonify({"status": "error", "advisory": "Error generating AI response."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
