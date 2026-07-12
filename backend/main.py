from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="African Financial Mentorship AI Platform API")

# Enable Cross-Origin Resource Sharing for your local Next.js environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "healthy", "message": "AI Mentorship Engine Online"}

@app.get("/api/v1/test-persona")
def test_persona():
    return {
        "persona": "Thrift Clothing Achiever",
        "archetype": "Driven/Resilient",
        "sample_response": "Success isn't given; you chase it down every single morning."
    }