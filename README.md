# 🚀 Agentic Bid & Proposal Response Engine

An AI-powered pre-sales automation assistant designed to streamline the evaluation of Request for Proposals (RFPs) and Request for Quotations (RFQs). This tool dynamically parses client requirements, runs an agentic Retrieval-Augmented Generation (RAG) audit against corporate credentials, forecasts Win Probability, auto-drafts proposal responses, and generates structured Statement of Work (SOW) deliverables.

---

## 🌟 Key Features

* **Multi-Agent Collaborative Pipeline:**
  * **Analyst Agent:** Extracts mandatory compliance clauses, SLA terms, and proposal questions from RFP text or files.
  * **Researcher Agent:** Employs vector similarity queries to find matching company experience and credentials.
  * **Scorer Agent:** Evaluates historical statistics to calculate Win Probability and recommends a **GO/NO-GO** decision.
  * **Writer Agent:** Synthesizes custom technical narrative responses referencing past projects.
  * **Reviewer Agent:** Flags compliance gaps and writes review commentary.
* **Role-Based Access Control (RBAC):**
  * **Bid Manager (`admin`):** Full privileges (create workspaces, override checklist status, upload capability records).
  * **Pre-Sales Writer (`writer`):** Modify proposal drafts and export responses.
  * **Executive Viewer (`viewer`):** View status dashboard, checklists, and download proposals.
* **Statement of Work (SOW) Estimator:** Automatically calculates labor headcount, man-months, milestones, and costs aligned to historical vertical metrics.
* **Mock ChromaDB (Cosine Vector Similarity):** Powered by custom TF-IDF cosine similarity, light stemming (handling suffix matching like *certified/certifications*), and soft length normalization (`doc_mag ** 0.75`) to run robust RAG checks without external API dependencies.
* **Word Document Compiler (.docx):** One-click exports of fully structured technical proposals with standard headings, drafts, and SOW tables.

---

## 📁 Project Structure

```bash
bid-proposal-engine/
├── backend/
│   ├── chromadb/            # Custom TF-IDF vector database emulation
│   ├── main.py              # FastAPI endpoints and permission gates
│   ├── database.py          # SQLite schema init and seed loader
│   ├── agents.py            # Multi-agent core pipeline logic
│   ├── document_parser.py   # PDF, DOCX, XLSX, and TXT parsing utilities
│   ├── scoring.py           # Win probability and budget alignment models
│   ├── requirements.txt     # Backend python dependencies
│   └── Dockerfile
├── frontend/
│   ├── app.py               # Streamlit application UI and template configs
│   └── Dockerfile
├── dataset.xlsx             # Seed data (Bid History and Capability Library)
├── docker-compose.yml       # Orchestrates frontend and backend containers
└── README.md
```

---

## 🛠️ Setup & Installation

### Option 1: Run Locally (Virtual Environment)

1. **Clone the Repository:**
   ```bash
   git clone git@github.com:muzzammilalam2/agentic-bid-response-engine.git
   cd agentic-bid-response-engine
   ```

2. **Setup the Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Run the FastAPI Backend:**
   ```bash
   cd backend
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Run the Streamlit Frontend:**
   *Open a separate terminal window and run:*
   ```bash
   cd frontend
   streamlit run app.py --server.port 8501
   ```
   Open `http://localhost:8501` in your browser.

---

### Option 2: Run with Docker Compose

Build and launch the entire stack in one command:
```bash
docker-compose up --build
```
* Backend starts on: `http://localhost:8000`
* Streamlit UI starts on: `http://localhost:8501`

---

## 🎯 Verification and Usage Guide

### 1. Ingesting Capabilities (Adding CVs/Case Studies)
* In the sidebar under **Ingest Capability Files**, select the domain (e.g., `IT Services`).
* Upload a professional CV or case study (e.g., `Eleanor Vance's CV`).
* Click **Upload to RAG Library**.

### 2. Testing Compliance (Pass/Fail Checks)
Create a new Workspace and select the **IT Services (Mobile Banking App)** prototype template or paste:
> *"The contractor must have a Lead Project Manager who is PMP certified and has experience with ISO 27001 implementations."*

* **PASS Response:** The engine stems terms (*certified* $\rightarrow$ *cert*, *implementations* $\rightarrow$ *implement*) to match the uploaded CV and marks the checklist status as **PASS**, displaying the CV snippet as evidence.
* **FAIL Response:** Change the text to require a missing framework (e.g., *"The contractor must use Quantum Cryptography"*). The lack of library data will output a **FAIL** checklist status.

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.
