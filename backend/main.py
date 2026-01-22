from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🔥 CORS (OBBLIGATORIO PER VERCEL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok per ora
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
z
