# Alexa + NVIDIA LLM Setup for FastTradeApp

This setup adds a **read-only Alexa skill webhook** to your backend so Alexa can ask your Fast Trade AI questions using your existing NVIDIA-compatible LLM configuration.

## Files added

- `backend/app/api/routes/alexa.py` — Alexa webhook endpoint
- `backend/examples/alexa_fasttrade_interaction_model.json` — interaction model to import into Alexa Developer Console

---

## 1) Configure your backend `.env`

Open `backend/.env` and confirm these values exist:

```env
LLM_PROVIDER=custom
LLM_API_KEY=your_nvidia_api_key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=mistralai/mistral-small-4-119b-2603

ALEXA_SKILL_NAME=Fast Trade AI
ALEXA_ALLOWED_SKILL_ID=
```

> If you leave `ALEXA_ALLOWED_SKILL_ID` blank, the endpoint will accept requests from any Alexa skill. For better security, paste your real Alexa Skill ID after creating the skill.

---

## 2) Start the backend

From `D:\FastTradeApp\backend`:

```powershell
D:\FastTradeApp\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Check:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/alexa/health`

---

## 3) Expose it with ngrok

In a new terminal:

```powershell
ngrok http 8000
```

Copy the **HTTPS** forwarding URL, for example:

```text
https://abc123.ngrok-free.app
```

Your Alexa endpoint becomes:

```text
https://abc123.ngrok-free.app/alexa/skill
```

---

## 4) Create the Alexa skill

1. Open the **Alexa Developer Console**.
2. Click **Create Skill**.
3. Skill name: `Fast Trade AI`
4. Choose **Custom** model.
5. Choose **Provision your own** backend.
6. Create the skill.

---

## 5) Import the interaction model

1. In the Alexa console, open **Build**.
2. Go to **JSON Editor**.
3. Paste the contents of `backend/examples/alexa_fasttrade_interaction_model.json`.
4. Click **Save Model**.
5. Click **Build Model**.

Invocation name in the sample: `fast trade assistant`

---

## 6) Set the endpoint

1. Open **Endpoint** in the Alexa console.
2. Select **HTTPS**.
3. Paste your ngrok URL with `/alexa/skill`.
4. Save.

If Alexa shows you the skill ID, copy it into:

```env
ALEXA_ALLOWED_SKILL_ID=amzn1.ask.skill.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Then restart the backend.

---

## 7) Test phrases

Try these in the Alexa simulator or app:

- `Alexa, open fast trade assistant`
- `Alexa, ask fast trade assistant for my portfolio summary`
- `Alexa, ask fast trade assistant what is my risk today`
- `Alexa, ask fast trade assistant for a market update`
- `Alexa, ask fast trade assistant what is RSI`
- `Alexa, ask fast trade assistant who is Warren Buffett`

---

## 8) Can this connect to your Fast Trade app AI later?

**Yes.** In this implementation, Alexa already reuses the backend AI route logic, so it can answer using your existing Fast Trade trading context.

### Safe next upgrades

1. **Account linking** for per-user identity
2. **Voice PIN / OTP confirmation** before any trade action
3. **Read-only portfolio mode** by default
4. Optional future intents for:
   - portfolio performance
   - open position alerts
   - scanner signal summaries
   - market sentiment briefings

> Recommendation: keep Alexa **read-only** first. Do not place live trades by voice until you add confirmation, authentication, and audit logging.
