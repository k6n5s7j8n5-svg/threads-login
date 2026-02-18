from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    print("LINEきた")
    print(request.json)
    return "OK", 200
