# Candidate Screening AI

AI-powered candidate screening platform that combines Retrieval-Augmented Generation (RAG), resume analysis, dynamic interview generation, and automated technical evaluation to simulate role-specific technical interviews.

---

## Overview

Technical interviews are often generic, repetitive, and difficult to scale consistently across candidates.

Candidate Screening AI addresses this by generating role-specific interview questions grounded in curated technical knowledge bases, adapting them to a candidate's resume, and providing automated evaluation with detailed feedback.

The system parses resumes, retrieves relevant concepts from technical textbooks using a RAG pipeline, generates personalized interview questions, evaluates responses, and produces a structured assessment report.

---

## Features

### Resume Analysis

* PDF and TXT resume support
* Skill extraction using Gemini
* Domain exposure identification
* Seniority classification (Junior, Mid, Senior)
* Experience summarization

### Retrieval-Augmented Generation

* Role-specific knowledge bases
* ChromaDB vector search
* Multi-query retrieval strategy
* Context-grounded question generation
* Traceability from questions back to source content

### Interview Engine

* Personalized technical assessments
* Dynamic question generation
* Session persistence
* Question skipping support
* Progressive interview flow

### AI Evaluation

* Per-question scoring
* Detailed answer feedback
* Overall assessment generation
* Strengths and improvement areas
* Candidate performance summary

### User Experience

* Professional assessment interface
* Resume upload workflow
* Real-time progress tracking
* Loading states and notifications
* Detailed post-interview analysis

---

## Architecture

```text
┌─────────────────────┐
│   Resume Upload     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Gemini Parser      │
│  • Skills           │
│  • Domains          │
│  • Seniority        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Candidate Profile   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Query Generation    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ChromaDB Retrieval  │
│     (RAG)           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Gemini Question     │
│ Generation          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Technical Interview │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Gemini Evaluation   │
│ • Score             │
│ • Feedback          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Overall Assessment  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Results Dashboard   │
└─────────────────────┘
```

---

## Tech Stack

| Layer        | Technology                               |
| ------------ | ---------------------------------------- |
| Frontend     | React 18 + Vite                          |
| Backend      | FastAPI                                  |
| Database     | SQLite + SQLAlchemy 2.0                  |
| LLM          | Google Gemini 2.5 Flash                  |
| Embeddings   | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB                                 |
| PDF Parsing  | PyMuPDF                                  |

---

## Project Structure

```text
candidate-screening-ai/
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── pages/
│       │   ├── UploadPage.jsx
│       │   ├── InterviewPage.jsx
│       │   └── ResultsPage.jsx
│       ├── services/
│       │   └── api.js
│       ├── App.jsx
│       └── main.jsx
│
├── backend/
│   ├── .env
│   ├── env.example
│   ├── requirements.txt
│   │
│   ├── api/
│   │   └── routes/
│   │       └── interview.py
│   │
│   └── app/
│       ├── main.py
│       │
│       ├── core/
│       │   ├── config.py
│       │   └── database.py
│       │
│       ├── models/
│       │   └── models.py
│       │
│       ├── schemas/
│       │   └── schemas.py
│       │
│       └── services/
│           ├── resume/
│           │   └── parser.py
│           │
│           ├── rag/
│           │   ├── ingest.py
│           │   ├── retriever.py
│           │   └── question_generator.py
│           │
│           ├── interview/
│           │   └── orchestrator.py
│           │
│           └── evaluation/
│               └── evaluator.py
│
├── knowledge_base/
│   ├── ai_ml/
│   └── backend/
│
└── vector_store/
```

---

## How It Works

### 1. Resume Processing

The candidate uploads a resume.

Gemini extracts:

* Technical skills
* Experience summary
* Domain exposure
* Seniority level

This structured profile becomes the foundation for the rest of the interview.

### 2. Context Retrieval

The system builds multiple retrieval queries using:

* Candidate skills
* Domain experience
* Role selected
* Seniority level

Relevant chunks are retrieved from ChromaDB using locally generated embeddings.

### 3. Question Generation

Retrieved knowledge-base content is combined with resume insights and sent to Gemini.

The model generates a balanced technical assessment consisting of:

* Easy questions
* Medium questions
* Hard questions

All questions are grounded in retrieved context rather than generated from model memory alone.

### 4. Evaluation

Each submitted answer is evaluated independently.

The evaluator generates:

* Numerical score
* Written feedback
* Strengths and weaknesses

At the end of the interview, an overall assessment is generated from all candidate responses.

---

## Setup

### Prerequisites

* Python 3.11+
* Node.js 18+
* Google Gemini API Key

Generate a Gemini API key:

https://aistudio.google.com

---

### Backend Setup

```bash
git clone <repository-url>

cd candidate-screening-ai/backend

uv venv

source .venv/bin/activate
```

Install dependencies:

```bash
uv pip install -r requirements.txt
```

Create environment file:

```bash
cp env.example .env
```

Add your Gemini API key:

```env
GOOGLE_API_KEY=your_api_key_here
```

---

### Knowledge Base Ingestion

Before running the application, ingest the knowledge base.

```bash
python -m app.services.rag.ingest --role ai_ml
```

For backend interview content:

```bash
python -m app.services.rag.ingest --role backend
```

To rebuild the vector database:

```bash
python -m app.services.rag.ingest --role ai_ml --reset
```

---

### Start Backend

```bash
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Swagger Documentation:

```text
http://localhost:8000/docs
```

---

### Start Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## API Endpoints

| Method | Endpoint                                        | Description              |
| ------ | ----------------------------------------------- | ------------------------ |
| POST   | `/sessions`                                     | Create interview session |
| POST   | `/sessions/{id}/resume`                         | Upload resume            |
| GET    | `/sessions/{id}/next-question`                  | Retrieve next question   |
| POST   | `/sessions/{id}/questions/{question_id}/answer` | Submit answer            |
| POST   | `/sessions/{id}/questions/{question_id}/skip`   | Skip question            |
| GET    | `/sessions/{id}/summary`                        | Final assessment report  |

---

## Design Decisions

### Multi-Query Retrieval

A single retrieval query often produces generic results.

Instead, the system generates multiple targeted queries from:

* Skills
* Domains
* Role requirements
* Seniority level

Results are merged and deduplicated to improve context quality.

### Local Embeddings

Embeddings are generated locally using:

```text
all-MiniLM-L6-v2
```

This eliminates embedding API costs and keeps retrieval fast.

### Role-Specific Knowledge Bases

Questions are generated from curated technical resources rather than relying solely on LLM knowledge.

This improves consistency and reduces hallucination.

### Traceability

Every generated question stores:

* Source topics
* Retrieved chunk identifiers

This makes the question generation process explainable and auditable.

### SQLite First

SQLite keeps local development simple and portable.

The architecture can be migrated to PostgreSQL with minimal changes.

---

## Environment Variables

| Variable           | Description                |
| ------------------ | -------------------------- |
| GOOGLE_API_KEY     | Gemini API key             |
| GOOGLE_MODEL       | Gemini model               |
| DATABASE_URL       | Database connection string |
| CHROMA_PERSIST_DIR | ChromaDB storage location  |
| KNOWLEDGE_BASE_DIR | Knowledge base directory   |
| EMBEDDING_MODEL    | Embedding model            |
| CHUNK_SIZE         | Retrieval chunk size       |
| CHUNK_OVERLAP      | Chunk overlap              |
| RETRIEVAL_TOP_K    | Number of retrieved chunks |

---

## Future Improvements

* Voice-based interviews
* Resume vs Job Description matching
* Recruiter dashboard
* PDF assessment exports
* Authentication and user accounts
* Additional engineering roles
* PostgreSQL deployment
* Cloud-hosted vector database

---

## Author

Built by Nishik Varma as a practical exploration of applied AI systems involving RAG, LLM orchestration, vector search, and automated technical assessment.
