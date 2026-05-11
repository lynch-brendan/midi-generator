# Muse — AI Musician

## What this is
Muse (museaimusician.com) is a web app where users describe a musical idea in plain English and instantly get 5 playable audio variations plus downloadable MIDI files. The core value prop: **audio-first idea generation for musicians**. Users hear the results immediately, download MIDI if they like something, and drag it into their DAW. All output is royalty free.

Target users: music producers, beatmakers, composers who want fast inspiration and starting points — not finished songs.

## Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) for generation, `claude-haiku-4-5-20251001` for the speech bubble reaction
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
core/models.py             — SQLAlchemy: User, Folder, SavedFile, Project
core/stripe_client.py      — Stripe subscription management
core/storage.py            — Cloudflare R2 upload/retrieval
prompts/system_prompt.txt  — Music theory system prompt for Claude (the "musician brain")
web/index.html             — Full SPA (~2970 lines): UI, streaming, autoplay, library, session
web/terms.html             — Terms of service
web/privacy.html           — Privacy policy
```

## Generation flow
1. User submits prompt → `POST /api/generate`
2. Server streams SSE events to frontend:
   - `thought` tokens — Haiku writes a funny one-liner reacting to the prompt (e.g. "dark jazz piano?? this is literally my moment"), typed into the speech bubble character by character
   - `meta` — instrument detected from Claude's streaming JSON
   - `variation` (×5) — each variation as it completes (MIDI written + WAV rendered synchronously before event is sent)
   - `done`
3. Frontend shows 5 animated "thought clouds", auto-plays audio sequentially
4. User clicks a cloud to expand variation detail panel (audio player, MIDI/WAV download, save, keep)

## Speech bubble states
- **Generate clicked:** Haiku one-liner types in character-by-character (e.g. "lofi beats say less")
- **First variation ready:** fades to "check this out"
- **All done:** fades to "what's next?"
- **Idle:** "I'll play any instrument — what do you want to hear?"

## Auto-play behaviour
- Auto-play toggle (on by default): plays variation 1 when ready, chains through all 5 via `audio.ended`
- WAV is rendered synchronously before the variation event is sent — file is guaranteed to exist when autoplay fires
- If tab is hidden (user switches apps), autoplay pauses and resumes via `visibilitychange` event
- If a variation fails to process, it's skipped silently — doesn't kill the rest of the session

## Session & Projects ("Keep This")
- Users can click **♥ keep this** on any variation to add it to the current session
- Session panel (right side) collects kept variations with name/tempo/key metadata
- Session can be saved as a named **Project** → appears in Library
- Projects are stored in DB with files uploaded to R2
- `saveProject()` works from both the session panel and the save project modal

## Conversation history
- After each generation, a summary is added to `conversationHistory`
- User can click **Reply** to do a follow-up generation with context
- History is capped at 4 turns before sending to Claude to prevent API issues
- Fresh generation (new prompt) always resets history

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
| GET/POST | `/api/projects` | List/create projects |
| DELETE | `/api/projects/{id}` | Delete project |
| GET | `/api/projects/{id}/files` | List files in project |

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

## Soundfont
- MuseScore General SF2 (~206MB, MIT licensed) — downloaded at Docker build time from OSUOSL mirror
- Stored at `soundfonts/MuseScore_General.sf2`; `audio_renderer.py` falls back to other locations if missing
- Run `setup.sh` to download locally for dev

## Key/scale design
- Each variation has its own `key` and `scale_notes` (not global) — intentional, varied tonal centers
- System prompt KEY RULE enforces no two variations share the same key
- `key` shown in session panel item meta line and in detail panel

## Code conventions
- No JS framework — vanilla JS only, no build step
- Keep all frontend in `web/index.html` (one file)
- Backend is one file (`server.py`) importing from `core/`
- Prompt engineering lives in `prompts/system_prompt.txt` — this is the main lever for output quality
- Always commit and push after changes so Railway deploys
