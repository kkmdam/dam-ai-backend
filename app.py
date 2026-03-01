from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os
import json

app = Flask(__name__)
CORS(app)

# Fetch key and immediately strip any accidental invisible spaces
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
WEATHER_KEY = os.environ.get("WEATHER_API_KEY", "").strip()

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # Using the newest, fastest Gemini model
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
        return jsonify({"status": "error", "message": "VERCEL ERROR: GEMINI_API_KEY is missing from environment variables!"}), 400
        
    prompt = f"""
    You are an AI assistant for a dam control room. Extract the following parameters from the user's message and return ONLY a strict JSON object. DO NOT output any markdown formatting, backticks, or extra words. If a value is not mentioned, use null.
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
        raw_text = response.text.strip()
        
        # Aggressively clean the AI's response in case it uses markdown formatting
        clean_json = raw_text.replace('```json', '').replace('```', '').strip()
        
        try:
            parsed_data = json.loads(clean_json)
            return jsonify({"status": "success", "data": parsed_data})
        except Exception as json_err:
            return jsonify({"status": "error", "message": f"AI MATH ERROR. The AI replied with: {raw_text}"}), 400
            
    except Exception as api_err:
        return jsonify({"status": "error", "message": f"GOOGLE API CRASH: {str(api_err)}"}), 400

@app.route('/api/generate-advisory', methods=['POST'])
def generate_advisory():
    data = request.get_json(silent=True) or {}
    
    if not GEMINI_KEY:
        return jsonify({"status": "error", "advisory": "VERCEL ERROR: GEMINI_API_KEY is missing!"})
        
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
