from flask import Flask, request, jsonify
import os, requests

app = Flask(__name__)

GROQ_KEY = os.getenv("GROQ_API_KEY")
MY_API_KEY = os.getenv("MY_WHATSAPP_AGENT_API_KEY") # WhatsApp ne jo di hai

@app.route('/', methods=['GET'])
def home():
    return "Agent Backend Live"

@app.route('/chat', methods=['POST'])
def chat():
    # 1. Check WhatsApp ki API Key
    auth = request.headers.get('Authorization') or request.headers.get('x-api-key')
    if MY_API_KEY and MY_API_KEY not in str(auth):
        return jsonify({"error": "Invalid API Key"}), 401

    data = request.json
    user_msg = data.get('message') or data.get('query') or data.get('text') or ""

    # 2. Free Model (Groq) se jawab lo
    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role":"system","content":"You are OMEGA PRIME, helpful AI by M. Hassan. Reply in same language as user."},
                    {"role":"user","content": user_msg}
                ]
            }, timeout=15)
        reply = res.json()['choices'][0]['message']['content']
    except Exception as e:
        reply = f"Error: {e}"

    # 3. WhatsApp ko wapas bhejo
    return jsonify({"reply": reply, "response": reply, "answer": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
