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

### English (`en-US`)

1. In the Alexa console, open **Build**.
2. Go to **JSON Editor**.
3. Paste the contents of `backend/examples/alexa_fasttrade_interaction_model.json`.
4. Click **Save Model**.
5. Click **Build Model**.

Invocation name in the sample: `open fast trade`

### Hindi (`hi-IN`)

1. In the Alexa console, add the **Hindi (IN)** locale.
2. Open that locale's **JSON Editor**.
3. Paste `backend/examples/alexa_fasttrade_interaction_model_hi_IN.json`.
4. Save and build the Hindi model.

> With `hi-IN`, the backend now responds in simple Hindi or Hinglish for voice-friendly answers.

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

- `Alexa, open open fast trade`
- `Alexa, ask open fast trade for my portfolio summary`
- `Alexa, ask open fast trade what is my risk today`
- `Alexa, ask open fast trade for a market update`
- `Alexa, ask open fast trade what is RSI`
- `Alexa, ask open fast trade who is Warren Buffett`
- `Alexa, ask open fast trade buy Reliance for tomorrow`
- `Alexa, confirm trade`
- `Alexa, cancel trade`
- `Alexa, ask open fast trade for my morning briefing`
- `Alexa, ask open fast trade remember that I prefer low risk trades`
- `Alexa, ask open fast trade remind me to review Nifty at 9 30 AM`
- `Alexa, ask open fast trade what do you remember`
- `Alexa, ask open fast trade summarize market news`
- `Alexa, ask open fast trade what is on my watchlist`
- `Alexa, ask open fast trade add Reliance and Infosys to my watchlist`
- `Alexa, ask open fast trade clear my watchlist`
- `Alexa, ask open fast trade what is the market sentiment`
- `Alexa, ask open fast trade top movers today`
- `Alexa, ask open fast trade earnings this week`
- `Alexa, ask open fast trade give me a trading lesson`
- `Alexa, ask open fast trade explain the strategy iron condor`
- `Alexa, ask open fast trade log a trade note I exited early due to fear`
- `Alexa, open open fast trade and say मार्केट अपडेट`
- `Alexa, open open fast trade and say मेरी watchlist में Reliance जोड़ो`

## 8) Jarvis-style assistant features

This skill now supports light Jarvis-style features while the backend is running:

- **Morning briefing** for a quick start-of-day summary
- **Memory notes** like preferred risk profile or focus stock
- **Session reminders** such as review Nifty at 9 30 AM
- **Session watchlist memory** so you can add names by voice and ask for a summary later
- **Market sentiment check** for a quick bullish, bearish, or mixed mood update
- **General AI Q and A** along with FastTrade market context

> Note: memory notes, reminders, journal entries, and the Alexa watchlist are now stored in the database when the backend DB is available. If the DB is temporarily unreachable, the skill falls back to session memory.

---

## 9) Safer voice trading behavior

Voice trading is implemented in a **safe confirmation-first mode**.

- A trade-style request like `buy Reliance` is treated as a **draft paper-trade instruction**.
- Alexa asks for confirmation before continuing.
- By default, **live voice trading stays disabled** for safety.

Optional env flag:

```env
ALEXA_VOICE_TRADING_ENABLED=false
```

> Recommendation: keep this `false` unless you later build a full confirmation, authentication, and broker-review flow.

---

## 9) Can this connect to your Fast Trade app AI later?

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

---

## 10) Proactive Alexa alerts (real alerts without asking)

Fast Trade now includes a backend foundation for **Alexa proactive alerts** tied to the existing notification system.

### Backend env vars

Add these to `backend/.env`:

```env
ALEXA_PROACTIVE_ALERTS_ENABLED=true
ALEXA_PROACTIVE_CLIENT_ID=your_lwa_client_id
ALEXA_PROACTIVE_CLIENT_SECRET=your_lwa_client_secret
ALEXA_PROACTIVE_STAGE=development
```

### Alexa Developer Console / manifest requirements

Your skill manifest must include:

- permission: `alexa::devices:all:notifications:write`
- publication event: `AMAZON.MessageAlert.Activated`
- subscription event handling for `AlexaSkillEvent.ProactiveSubscriptionChanged`

### User-side requirement

In the Alexa app, enable **Notifications** for your skill. Alexa sends the subscription event to `/alexa/skill`, and the backend records the subscribed user for future alerts.

### Test endpoint

You can send a test proactive event with:

```text
POST /alexa/proactive/test
GET  /alexa/proactive/status
```

Once configured, existing **high / critical** Fast Trade notifications such as stop-loss hits, trade failures, margin warnings, and important alerts can fan out to Alexa proactively.
