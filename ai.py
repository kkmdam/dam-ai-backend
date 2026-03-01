from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
import os
import json

app = Flask(__name__)
CORS(app)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
WEATHER_KEY = os.environ.get("WEATHER_API_KEY", "").strip()

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

def get_kakkayam_weather():
    lat, lon = "11.54", "75.92"
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
    try:
        response = requests.get(url).json()
        rain_total = sum(item['rain']['3h'] for item in response.get('list', [])[:8] if 'rain' in item and '3h' in item['rain'])
        return f"Expected rainfall in next 24hrs: {round(rain_total, 1)} mm."
    except Exception:
        return "Weather data currently unavailable."

@app.route('/api/parse-plan', methods=['POST'])
def parse_plan():
    if not GEMINI_KEY:
        return jsonify({"status": "error", "message": "NEW SERVER ERROR: GEMINI_API_KEY is missing!"}), 400

    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '')

    prompt = f"""
    Extract parameters from this message into a strict JSON object: "{user_message}"
    Format: {{"target_wl": float, "time_hours": float, "inflow": float, "powerhouse": float}}
    Return ONLY the JSON. No markdown. If missing, use null.
    """

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip().replace('```json', '').replace('```', '')
        parsed = json.loads(raw)
        return jsonify({"status": "success", "data": parsed})
    except Exception as e:
        ai_reply = response.text if 'response' in locals() else 'None'
        return jsonify({"status": "error", "message": f"AI CRASH: {str(e)} | AI SAID: {ai_reply}"}), 400

@app.route('/api/generate-advisory', methods=['POST'])
def generate_advisory():
    if not GEMINI_KEY:
        return jsonify({"status": "error", "advisory": "NEW SERVER ERROR: API Key missing!"})
        
    data = request.get_json(silent=True) or {}
    forecast = get_kakkayam_weather()
    
    prompt = f"Chief Engineer AI for Kakkayam Dam. WL: {data.get('wlCur')}m, Target: {data.get('wlTar')}m, Time: {data.get('hours')}h, Spill: {data.get('qSpill')} cumecs. Weather: {forecast}. Write a short Risk Analysis and a WhatsApp advisory for the District Collector."
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"status": "success", "advisory": response.text, "weather": forecast})
    except Exception as e:
        return jsonify({"status": "error", "advisory": f"AI Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
