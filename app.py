from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os
import json

app = Flask(__name__)
CORS(app)

# Fetch keys securely
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
WEATHER_KEY = os.environ.get("WEATHER_API_KEY")

if GEMINI_KEY:
    # .strip() removes any accidental invisible spaces!
    genai.configure(api_key=GEMINI_KEY.strip())
    # Upgraded to Google's newest, most reliable model
    model = genai.GenerativeModel('gemini-1.5-flash')

def get_kakkayam_weather():
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

@app.route('/api/parse-plan', methods=['POST'])
def parse_plan():
    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '')
    
    if not GEMINI_KEY:
        return jsonify({"status": "error", "message": "CRASH: GEMINI_API_KEY is missing from Vercel Settings!"}), 400
        
    prompt = f"""
    You are an AI assistant for a dam control room. Extract the following parameters from the user's message and return ONLY a strict JSON object. Do not include markdown formatting. If a value is not mentioned, use null.
    User Message: "{user_message}"
    
    Expected JSON format:
    {{
      "target_wl": float,
      "time_hours": float,
      "inflow": float,
      "powerhouse": float
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        raw_text = response.text
        
        try:
            clean_json = raw_text.replace('```json', '').replace('```', '').strip()
            parsed_data = json.loads(clean_json)
            return jsonify({"status": "success", "data": parsed_data})
        except Exception as json_err:
            return jsonify({"status": "error", "message": f"AI did not return math. AI said: {raw_text}"}), 400
            
    except Exception as api_err:
        return jsonify({"status": "error", "message": f"GOOGLE API ERROR: {str(api_err)}"}), 400

@app.route('/api/generate-advisory', methods=['POST'])
def generate_advisory():
    data = request.get_json(silent=True) or {}
    
    if not GEMINI_KEY:
        return jsonify({"status": "error", "advisory": "GEMINI_API_KEY is missing!"})
        
    weather_forecast = get_kakkayam_weather()
    prompt = f"""
    You are the Chief Engineer AI for Kakkayam Dam. Current WL: {data.get('wlCur')}m, Target WL: {data.get('wlTar')}m. Timeframe: {data.get('hours')} hours. Planned Spillway Discharge: {data.get('qSpill')} cumecs. Weather Forecast: {weather_forecast}
    Write a short, professional "Risk & Weather Analysis". If discharge is high AND heavy rain is expected, warn them. Write a short official WhatsApp advisory for the District Collector.
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "advisory": response.text, "weather": weather_forecast})
    except Exception as e:
        return jsonify({"status": "error", "advisory": f"Google API Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
