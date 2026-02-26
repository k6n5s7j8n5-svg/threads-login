from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/webhook")
async def webhook(request: Request):
    return PlainTextResponse("OK", status_code=200)
