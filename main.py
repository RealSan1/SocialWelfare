from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import select
from db import engine, 복지서비스, 카테고리

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/services")
def get_services():
    """
    복지서비스 + 카테고리 JOIN API
    """
    with engine.connect() as conn:
        services = [dict(row) for row in conn.execute(select(복지서비스)).mappings().all()]
        categories = [dict(row) for row in conn.execute(select(카테고리)).mappings().all()]

        cat_map = {}
        for c in categories:
            sid = c["서비스ID"]
            cat_map.setdefault(sid, []).append(c["카테고리"])

        for s in services:
            s["카테고리"] = cat_map.get(s["서비스ID"], [])

    return {"data": services}


if __name__ == "__main__":
    import uvicorn, os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
