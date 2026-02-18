@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "ok", 200
    print("LINEきた")
    print(request.get_json(silent=True))
    return "ok", 200
