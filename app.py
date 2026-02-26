from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/")
def root():
    return {"ok": True}

@app.post("/webhook")
async def webhook():
    return PlainTextResponse("OK", status_code=200)
