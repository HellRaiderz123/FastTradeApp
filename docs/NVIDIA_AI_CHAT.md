# NVIDIA AI Chat for FastTradeApp

A simple ChatGPT-style AI chat endpoint and browser playground is available in the backend.

## Endpoints

- `GET /simple-ai/health`
- `POST /simple-ai/chat`
- `GET /simple-ai/playground`

## Start the backend

```powershell
D:\FastTradeApp\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Open in browser

```text
http://127.0.0.1:8000/simple-ai/playground
```

## API example

```powershell
$body = @{
  message = "Explain RSI like I am a beginner trader"
  history = @()
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/simple-ai/chat" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## Required env

Make sure `backend/.env` contains:

```env
LLM_PROVIDER=custom
LLM_API_KEY=your_nvidia_api_key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=mistralai/mistral-small-4-119b-2603
```
