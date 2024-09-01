from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from routers import images

app = FastAPI(title="Image CRUD", version="0.1.0")

app.include_router(images.router)

app.mount("/static", StaticFiles(directory="storage"), name="static")

# either start server with uvicorn in terminal, or run this file
if __name__ == "__main__":
    uvicorn.run(app="main:app", host="127.0.0.1", port=8000, reload=True)
