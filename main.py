from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from router import recruiter, vacancies, cv, candidates, attachments, chat, auth


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create a parent router with the prefix
api_router = APIRouter(prefix="/api/v1")

# Include all routers to the parent router
api_router.include_router(recruiter.router)
api_router.include_router(vacancies.router)
api_router.include_router(cv.router)
api_router.include_router(candidates.router)
api_router.include_router(attachments.router)
api_router.include_router(chat.router)
api_router.include_router(auth.router)

# Include the parent router in the app
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications!"}

@app.get("/api/v1")
async def api_root():
    return {"message": "Welcome to the API v1"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)