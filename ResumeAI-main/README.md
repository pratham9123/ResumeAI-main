# 🚀 ResumeAI – AI-Powered ATS & Resume Analysis with RAG

ResumeAI is an AI-powered ATS (Applicant Tracking System) simulator that compares candidate resumes against job descriptions. It provides deterministic scoring, skill gap analysis, and grounded, actionable feedback powered by Retrieval-Augmented Generation (RAG).

## 📖 Project Overview
ResumeAI evaluates resumes using a hybrid approach. It first runs a deterministic analysis to calculate an objective match score. It then leverages a FAISS-backed RAG pipeline to retrieve role-specific, expert resume-writing guidance. Finally, it uses Google Gemini to synthesize this guidance with the candidate's actual resume to produce highly actionable, personalized, and strictly grounded feedback.

## 📸 Screenshots

### Home
![Home](screenshots/home.png)

### Analyze
![Analyze](screenshots/analysis.png)

### History
![History](screenshots/history.png)

### Score Breakdown
![Score](screenshots/score.png)

### Skill Gap
![Skill](screenshots/skill.png)

### AI Feedback
![Feedback](screenshots/feedback.png)

## 🗂️ Project Structure

```
Resume Analyzer/
├── frontend/          # React + Vite + Tailwind CSS
├── backend/           # Node.js + Express (API Gateway)
└── ml-service/        # Python + Flask (ML/NLP Engine)
```

## ⚙️ Tech Stack
- **Frontend**: React, Vite, Tailwind CSS, Firebase Auth
- **Backend**: Node.js, Express, MongoDB, Firebase Admin
- **ML Service**: Flask, pdfplumber, sentence-transformers, scikit-learn
- **AI Layer**: Google Gemini / OpenAI GPT
## ⚙️ Tech Stack
- **Frontend**: React, Vite, Tailwind CSS, Firebase Auth
- **Backend**: Node.js, Express, MongoDB, Firebase Admin
- **ML Service**: Flask, pdfplumber, sentence-transformers, scikit-learn
- **AI Layer**: Google Gemini / OpenAI GPT

---

## 🏗️ Updated Architecture

```mermaid
graph TD
    User([User / Browser])
    React[React Frontend]
    Node[Node.js Backend]
    Mongo[(MongoDB)]
    Flask[Flask ML Service]
    Gemini[Gemini API]
    FAISS[(FAISS Index)]
    
    User -->|Uploads PDF & JD| React
    React -->|POST /api/analyze| Node
    Node -->|POST /analyze| Flask
    Node -.->|Save Analysis| Mongo
    
    subgraph "Flask ML Pipeline"
      Flask --> TextExtract[PDF Extraction]
      TextExtract --> Deterministic[Deterministic Scoring & Extraction]
      Deterministic --> RAG_Query[RAG Query Builder]
      RAG_Query --> Retriever[FAISS Retriever]
      Retriever -.-> FAISS
      Retriever --> LLM_Prompt[Grounded Prompt Builder]
      LLM_Prompt --> Gemini
      Gemini --> LLM_Parser[Strict JSON Parser]
    end
    
    LLM_Parser -->|Returns structured payload| Node
    Node -->|Returns full result| React
```

### End-to-End Request Flow
1. **User Upload**: A user uploads their PDF resume and pastes a job description.
2. **Backend Forwarding**: The React frontend sends this to the Node.js API, which forwards the file and text to the Flask ML Service.
3. **Deterministic Analysis**: The ML service extracts text, parses skills using a predefined database, computes a baseline semantic similarity between the resume and JD, and outputs a weighted score.
4. **Query Construction**: A RAG query is built using the detected missing skills and weak resume sections.
5. **Retrieval**: The system queries a local FAISS index containing expert resume guidance, filtering by the inferred target role.
6. **Gemini Grounding**: The retrieved guidance, deterministic scores, resume, and JD are combined into a strict JSON-escaped prompt.
7. **Synthesis**: Gemini generates actionable feedback based *only* on the retrieved chunks, returning structured JSON with source attributions.
8. **Persistence & Display**: The Node.js backend saves the final output to MongoDB and returns it to the React frontend for rendering.

---

## 🔍 Deterministic Scoring vs. RAG

### Existing Deterministic Resume-Scoring System
Before reaching the LLM, the system calculates an objective score:
`Score = (Core Skills × 0.4) + (Resume Quality × 0.4) + (Semantic Similarity × 0.1) + (Experience Signal × 0.1)`
This ensures candidates receive consistent, reproducible evaluations that don't fluctuate due to LLM temperature or hallucination.

### Why RAG Was Added
While the deterministic system provides accurate scores and identifies missing skills, it cannot explain *how* to fix them. Standard LLM prompts without RAG often generate generic, fluffy advice (e.g., "Add more impact"). RAG injects specific, expert-curated examples (e.g., "For a backend developer missing Docker, phrase your project like this...") ensuring the AI's advice is expert-level and highly actionable.

### Difference Between Semantic Job Matching and RAG
- **Semantic Job Matching** compares the *candidate's resume* directly against the *job description* using `all-MiniLM-L6-v2` to generate a 0-1 similarity score. It answers: "How well does this resume fit the job?"
- **RAG** compares the *candidate's weaknesses* against a database of *expert resume-writing tips* using the exact same embedding model. It answers: "What specific advice does this candidate need to improve their resume?"

---

## 🧠 Knowledge Base & Retrieval

### Knowledge-Base Structure
The raw knowledge resides in Markdown files under `ml-service/knowledge_base/data/`. These files are parsed into standardized chunks containing an `id`, `role`, `category`, `title`, `text`, `source`, and `tags`.

### Embedding Model
The system uses `sentence-transformers/all-MiniLM-L6-v2` (loaded via a thread-safe singleton) to convert text into dense 384-dimensional vectors. This model was chosen because it is incredibly fast, lightweight (~90MB), and runs efficiently on CPUs without requiring a GPU.

### FAISS Vector Index
Chunks are indexed using **FAISS (Facebook AI Similarity Search)** with a flat L2 index (`IndexFlatL2`). FAISS allows for lightning-fast nearest-neighbor lookups in memory.

### Query Construction & Retrieval
The `RetrievalQueryBuilder` generates a natural language search query based on the candidate's exact skill gaps and weak sections. 

During retrieval, the FAISS index calculates cosine similarity (derived from L2 distance on normalized vectors). The results are strictly filtered to only include chunks that match the candidate's `target_role` (or general advice), ensuring a Backend Developer doesn't receive UI/UX advice.

---

## 🤖 Gemini Grounding & Safety

### Gemini Grounding
The LLM prompt is heavily structured. The resume and job description are JSON-escaped inside `<UNTRUSTED_RESUME encoding="json-string">` tags to prevent prompt injection. The LLM is provided the deterministic scores, the retrieved guidance, and a strict JSON schema to follow.

### Source Attribution
Every piece of generated advice must include a `source_ids` array pointing back to the specific FAISS chunk `id`. The frontend renders this as a "Why this recommendation?" citation, building user trust.

### Fallback Behaviour
If the FAISS index is missing, or if retrieval fails, the system safely falls back to a legacy prompt. The LLM is instructed to provide the best possible advice using only the resume and JD, while the RAG metadata marks `fallbackUsed: true`.

---

## 🔌 API Contracts

### Request: `POST /api/analyze`
```http
POST /api/analyze HTTP/1.1
Authorization: Bearer <Firebase_JWT>
Content-Type: multipart/form-data; boundary=---Boundary

---Boundary
Content-Disposition: form-data; name="target_role"

backend_developer
---Boundary
Content-Disposition: form-data; name="job_description"

We are looking for a backend engineer familiar with Python, Docker, and PostgreSQL.
---Boundary
Content-Disposition: form-data; name="resume"; filename="resume.pdf"
Content-Type: application/pdf

<PDF Binary Data>
---Boundary--
```

### Response
```json
{
  "analysisId": "60d5ec49c1b...",
  "score": 82,
  "rag": {
    "enabled": true,
    "status": "success",
    "used": true,
    "fallbackUsed": false
  }
}
```

---

## 💻 Local Setup

### 1. Environment Variables
**Backend (`backend/.env`)**
```env
PORT=5000
MONGODB_URI=mongodb://localhost:27017/resumeai
FRONTEND_URL=http://localhost:3000
ML_SERVICE_URL=http://localhost:8000
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@...
CLOUDINARY_CLOUD_NAME=name
CLOUDINARY_API_KEY=123
CLOUDINARY_API_SECRET=abc
```

**ML Service (`ml-service/.env`)**
```env
GEMINI_API_KEY=AIzaSy...
RAG_ENABLED=1
RAG_TOP_K=5
RAG_MIN_SIMILARITY=0.25
GEMINI_TIMEOUT_MS=30000
```

### 2. Index-Building Command
Before running the ML service, you must build the FAISS index:
```bash
cd ml-service
python -m venv venv
# Windows: venv\Scripts\activate | Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m knowledge_base.build_index
```

### 3. Running the Application
**Backend:**
```bash
cd backend
npm install
npm run dev
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**ML Service:**
```bash
cd ml-service
# Assuming venv is activated
python app.py
```

---

## 🧪 Testing & Evaluation

### Running Tests
The ML service has a comprehensive pytest suite (72 tests) verifying deterministic scoring, RAG retrieval, error handling, and prompt generation.
```bash
cd ml-service
python -m pytest tests/
```

### Running Evaluation
The system includes an automated evaluation pipeline using LLM-as-a-judge to measure RAG retrieval precision, grounding rates, and subjective feedback quality.
```bash
cd ml-service
python scripts/run_rag_eval.py
```
Reports are output to `ml-service/evaluation_reports/`.

---

## ☁️ Deployment

1. **MongoDB**: Use MongoDB Atlas.
2. **Frontend (Vercel/Netlify)**:
   - Set build command to `npm run build`.
   - Set `REACT_APP_API_URL` to your Node backend URL.
3. **Backend (Render/Railway)**:
   - Deploy the `backend` folder.
   - Set `ML_SERVICE_URL`, `MONGODB_URI`, `CLOUDINARY_*`, and `FIREBASE_*`.
4. **ML Service (Render/Railway/GCP)**:
   - Deploy the `ml-service` folder.
   - Set `GEMINI_API_KEY`, `RAG_ENABLED=1`.
   - Start command: `gunicorn app:app -w 4 -k gevent`
   - *Note*: If deploying multiple Gunicorn workers without shared memory, set `SEMANTIC_MODEL_SHARED=0` to load the embedding model per-worker.

---

## 🛡️ Security, Privacy, and Limitations

### Security and Privacy
- **Prompt Injection Defense**: User resumes and job descriptions are serialized via `json.dumps()` and placed inside XML-like tags (e.g. `<UNTRUSTED_RESUME encoding="json-string">`). This prevents users from breaking out of the prompt layout to issue rogue commands to the LLM.
- **Data Leakage**: The ML service does not persist resumes. PDFs are processed in memory. The Node.js backend saves them securely to Cloudinary.

### Known Limitations
- The PDF text extractor (`pdfplumber`) struggles with complex multi-column layouts.
- FAISS is currently running entirely in-memory. 
- The knowledge base contains synthetic sample data; it needs to be populated with real expert guidance before widespread production use.

### Future Improvements
- Move FAISS to a persistent vector database (e.g., Pinecone, Milvus) if the knowledge base scales beyond memory limits.
- Add an admin dashboard to curate and update the knowledge base without requiring a redeploy.