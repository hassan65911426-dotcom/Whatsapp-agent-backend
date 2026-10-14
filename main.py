from flask import Flask, request, jsonify
import os, requests
app = Flask(__name__)
MY_API_KEY = os.getenv("MY_API_KEY") or os.getenv("WHATSAPP_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
@app.route("/", methods=["GET","POST"])
def home():
    if request.method=="GET":
        return "OMEGA Live",200
    auth = request.headers.get("Authorization","") + str(request.headers)
    print(f"Headers: {request.headers}")
    data = request.get_json(silent=True) or {}
    print(f"Body: {data}")
    user_msg = data.get('message') or data.get('text') or data.get('query') or data.get('prompt') or ""
    if not user_msg:
        return jsonify({"reply":"Hi I'm OMEGA! Ask me anything"}),200
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {GROQ_KEY}"},json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"You are OMEGA PRIME by M. Hassan."},{"role":"user","content":user_msg}]},timeout=20)
        reply = r.json()['choices'][0]['message']['content']
    except Exception as e:
        reply=f"Error {e}"
    return jsonify({"reply":reply,"message":reply})
