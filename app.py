from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    print("LINE webhook:", body.decode())
    return {"ok": True}
