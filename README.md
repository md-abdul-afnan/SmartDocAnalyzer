# Smart Document Analyzer

Beginner-friendly full-stack mini project for document intelligence:
- Upload PDF, scanned docs, and images
- Extract text via OCR
- Summarize content into short summary + key points
- Describe uploaded images using AI (when API key is available)
- View animated results in a modern React UI

## Project Structure

```text
PRTFT Project/
  backend/
    app/
      main.py
      models.py
      routers/analyze.py
      services/ai_service.py
      services/extractors.py
    requirements.txt
    .env.example
  frontend/
    src/App.jsx
    src/main.jsx
    src/index.css
    package.json
```

## Backend Setup (FastAPI)

1. Open terminal in `backend`:
   ```bash
   cd backend
   ```
2. Create virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate it:
   - Windows PowerShell:
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Create `.env` file from example:
   ```bash
   copy .env.example .env
   ```
6. Add your OpenAI key in `.env`:
   ```env
   OPENAI_API_KEY=your_real_key_here
   ```
7. Run server:
   ```bash
   uvicorn app.main:app --reload
   ```

Backend runs at `http://127.0.0.1:8000`.

### Important OCR Requirement (Tesseract Engine)

You must install the native Tesseract app separately:
- Windows: Install Tesseract OCR and add it to PATH.
- If not in PATH, set this in `extractors.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```

## Frontend Setup (React + Tailwind + Framer Motion)

1. Open terminal in `frontend`:
   ```bash
   cd frontend
   ```
2. Install packages:
   ```bash
   npm install
   ```
   This includes:
   - `framer-motion` (animations)
   - `tailwindcss` (styling)
   - `jspdf` (bonus PDF download)
3. Start frontend:
   ```bash
   npm run dev
   ```

Frontend runs at `http://127.0.0.1:5173`.

## API Endpoints

### 1) Upload + Analyze

- **POST** `/api/upload`
- Query param:
  - `language` (default `eng`) for OCR language
- Form-data:
  - `file`: PDF or image file (`.pdf`, `.png`, `.jpg`, `.jpeg`)

Response format:

```json
{
  "extracted_text": "...",
  "summary": "...",
  "key_points": ["...", "..."],
  "image_description": "..."
}
```

### 2) Summarize Raw Text

- **POST** `/api/summarize`
- JSON body:
```json
{
  "text": "Your long text here..."
}
```

## Example API Usage

### Upload file via cURL

```bash
curl -X POST "http://127.0.0.1:8000/api/upload?language=eng" \
  -F "file=@sample.pdf"
```

### Summarize text via cURL

```bash
curl -X POST "http://127.0.0.1:8000/api/summarize" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"This is a sample document text to summarize.\"}"
```

## Implemented Animations (Framer Motion)

- Page load fade-in
- Upload box hover scale effect
- Analyze button tap/press animation
- Loading animation (bouncing dots)
- Result panel smooth entry + gravity-like drop spring
- Extracted text slides in from left
- Summary fades in
- Key points appear with staggered animation

## Error Handling Included

- Invalid file type check
- Empty extracted text check
- Summarization failure handling
- API response and UI error messaging

## Notes

- If `OPENAI_API_KEY` is missing, text summarization falls back to HuggingFace BART.
- Image description is only generated when OpenAI API key is configured.
- Handwritten OCR support is basic and depends heavily on image quality.
