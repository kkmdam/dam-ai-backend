import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# The ultimate CORS override
CORS(app, resources={r"/api/*": {"origins": "*"}})

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
WEATHER_KEY = os.environ.get("WEATHER_API_KEY", "").strip()

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Google Server Error: {response.status_code} - {response.text}")
        
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def get_kakkayam_weather():
    lat, lon = "11.54", "75.92"
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
    try:
        resp = requests.get(url).json()
        rain_total = sum(item['rain']['3h'] for item in resp.get('list', [])[:8] if 'rain' in item and '3h' in item['rain'])
        return f"Expected rainfall in next 24hrs: {round(rain_total, 1)} mm."
    except Exception:
        return "Weather data currently unavailable."

# Added 'OPTIONS' to manually catch and approve browser preflight checks
@app.route('/api/parse-plan', methods=['POST', 'OPTIONS'])
def parse_plan():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    if not GEMINI_KEY:
        return jsonify({"status": "error", "message": "GEMINI_API_KEY is missing!"}), 400

    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '')

    prompt = f"""
    Extract parameters from this message into a strict JSON object: "{user_message}"
    Format: {{"target_wl": float, "time_hours": float, "inflow": float, "powerhouse": float}}
    Return ONLY the JSON. No markdown. If missing, use null.
    """

    try:
        raw_text = call_gemini(prompt)
        clean_json = raw_text.strip().replace('```json', '').replace('```', '')
        parsed = json.loads(clean_json)
        return jsonify({"status": "success", "data": parsed})
    except Exception as e:
        return jsonify({"status": "error", "message": f"DIRECT CONNECTION CRASH: {str(e)}"}), 400

@app.route('/api/generate-advisory', methods=['POST', 'OPTIONS'])
def generate_advisory():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    if not GEMINI_KEY:
        return jsonify({"status": "error", "advisory": "API Key missing!"})
        
    data = request.get_json(silent=True) or {}
    forecast = get_kakkayam_weather()
    
    prompt = f"Chief Engineer AI for Kakkayam Dam. WL: {data.get('wlCur')}m, Target: {data.get('wlTar')}m, Time: {data.get('hours')}h, Spill: {data.get('qSpill')} cumecs. Weather: {forecast}. Write a short Risk Analysis and a WhatsApp advisory for the District Collector."
    
    try:
        advisory_text = call_gemini(prompt)
        return jsonify({"status": "success", "advisory": advisory_text, "weather": forecast})
    except Exception as e:
        return jsonify({"status": "error", "advisory": f"AI Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
