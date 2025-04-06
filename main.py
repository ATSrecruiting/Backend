from fastapi import FastAPI
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

app.include_router(recruiter.router)
app.include_router(vacancies.router)
app.include_router(cv.router)
app.include_router(candidates.router)
app.include_router(attachments.router)
app.include_router(chat.router)
app.include_router(auth.router)


@app.get("/")
async def root():
    return {"message": "Hello Bigger Applications!"}


# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
