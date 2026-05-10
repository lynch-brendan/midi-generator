# Muse — AI Musician

## What this is
Muse (museaimusician.com) is a web app where users describe a musical idea in plain English and instantly get 5 playable audio variations plus downloadable MIDI files. The core value prop: **audio-first idea generation for musicians**. Users hear the results immediately, download MIDI if they like something, and drag it into their DAW. All output is royalty free.

Target users: music producers, beatmakers, composers who want fast inspiration and starting points — not finished songs.

## Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) for generation, `claude-haiku-4-5-20251001` for thinking stream
- **Audio:** FluidSynth CLI (MIDI→WAV), pure Python MIDI writer (`core/midi_writer.py`)
- **Frontend:** Single-file vanilla HTML/CSS/JS SPA (`web/index.html`), no build tools
- **DB:** PostgreSQL via SQLAlchemy (optional — app degrades gracefully without it)
- **Storage:** Cloudflare R2 for drum kits and saved files
- **Billing:** Stripe (Free / Creator $12/mo / Pro $20/mo)
- **Auth:** Google OAuth + JWT cookie
- **Hosting:** Railway (autodeploys from GitHub main branch)
- **Domain:** museaimusician.com via Cloudflare proxy (Full SSL mode)

## Key files
```
server.py                  — FastAPI app: SSE generation endpoint, auth, Stripe, rate limiting
core/claude_client.py      — Claude API: stream_thinking() + stream_variations(), prompt caching
core/midi_writer.py        — Pure Python binary MIDI writer (no external deps)
core/audio_renderer.py     — FluidSynth subprocess wrapper (MIDI → WAV)
core/drum_synth.py         — Sample-based drum rendering from R2 kits
core/drum_kits.py          — Fetches/caches drum kit index from R2
core/expression.py         — Maps expression levels to pitch bend/vibrato per instrument
core/variations.py         — Validation and sanitization of Claude's JSON output
core/auth.py               — Google OAuth flow, JWT create/validate
core/models.py             — SQLAlchemy: User, Folder, SavedFile
core/stripe_client.py      — Stripe subscription management
core/storage.py            — Cloudflare R2 upload/retrieval
prompts/system_prompt.txt  — Music theory system prompt for Claude (the "musician brain")
web/index.html             — Full SPA (~2000 lines): UI, streaming, autoplay, library
web/terms.html             — Terms of service
web/privacy.html           — Privacy policy
```

## Generation flow
1. User submits prompt → `POST /api/generate`
2. Server streams SSE events to frontend:
   - `thought` tokens — Haiku thinks out loud (typed into search box in real time)
   - `meta` — instrument and key detected from Claude's streaming JSON
   - `variation` (×5) — each variation as it completes (MIDI written + WAV rendered)
   - `done`
3. Frontend shows 5 animated "thought clouds", auto-plays audio sequentially
4. User clicks a cloud to expand variation detail panel (audio player, MIDI/WAV download, save)

## Frontend behaviour notes
- Auto-play toggle (on by default): plays variation 1 when ready, chains through all 5 via `audio.ended`
- Audio unlock: fires a silent AudioContext on Generate click to bypass Chrome autoplay policy
- Thinking stream: Haiku tokens typed into the input box in italic while Claude generates
- Speech bubble states: idle → "Let me think…" → "here's some ideas" → "what else do you want to hear?"
- Variations displayed as floating thought clouds around an animated stick figure character
- Clicking a cloud opens a detail panel below with audio player, download buttons, save-to-folder

## API endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate` | SSE stream of thought + variations |
| GET | `/auth/google` | Start Google OAuth |
| GET | `/auth/callback` | Complete OAuth, set JWT cookie |
| POST | `/auth/logout` | Clear cookie |
| GET | `/auth/me` | Current user |
| POST | `/api/stripe/checkout/{plan}` | Create Stripe checkout session |
| POST | `/api/stripe/webhook` | Stripe webhook handler |
| GET | `/api/stripe/status` | User's plan + usage |
| POST | `/api/stripe/cancel` | Cancel subscription |
| GET/POST/DELETE | `/api/folders` | Library folder management |
| POST | `/api/save` | Save variation to library |
| GET/DELETE | `/api/saved` | List/delete saved files |

## Tiers
- **Free:** 3 generations/day (anonymous IP), 10 lifetime (signed in)
- **Creator:** $12/mo, 300 generations/month
- **Pro:** $20/mo, 1000 generations/month
- **Admin:** unlimited (set via `ADMIN_EMAILS` or `ADMIN_IPS` env vars)

## Environment variables needed
`ANTHROPIC_API_KEY`, `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `APP_URL`, `STRIPE_SECRET_KEY`, `STRIPE_CREATOR_PRICE_ID`, `STRIPE_PRO_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`

## Deploy
- Push to `main` → Railway autodeploys
- `git push origin main` is all that's needed
- Railway reads `PORT` env var, runs `python server.py`

## Code conventions
- No JS framework — vanilla JS only, no build step
- Keep all frontend in `web/index.html` (one file)
- Backend is one file (`server.py`) importing from `core/`
- Prompt engineering lives in `prompts/system_prompt.txt` — this is the main lever for output quality
- Always commit and push after changes so Railway deploys
