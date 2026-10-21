# WHOOP MCP · Triathlon Readiness

A Python [FastMCP](https://gofastmcp.com) server for the **WHOOP API v2**. It also runs a live
**Watermelon UI** dashboard on `http://localhost:8000`. Claude reads your recovery, strain, sleep and trends,
coaches you, and pushes its guidance onto the dashboard in real time.

```
Claude Code ──stdio──▶ whoop_mcp serve ──▶ WHOOP API v2 (OAuth2, auto-refresh)
                             │
                             └─ starts ─▶ FastAPI :8000 ──▶ React + Tailwind + Radix + Motion (Watermelon UI)
                                            ▲  SSE
              update_dashboard_insights ──▶ ~/.whoop-mcp/insights.json
```

## MCP tools

| Tool | Returns |
|---|---|
| `get_whoop_recovery(date)` | Recovery %, readiness zone, HRV vs 7-day baseline, RHR, SpO₂, skin temp and its deviation, respiratory rate, estimated stress, target strain band |
| `get_whoop_strain_and_activities(days_back)` | Day strain per day, plus workouts classified swim / bike / run, each with duration, strain, average/max HR, kJ, distance and Z0–Z5 minutes. Also per-discipline totals |
| `get_whoop_sleep_and_debt(date)` | Performance, efficiency, consistency, hours slept vs needed (with breakdown), awakenings, stages (SWS/REM/light/awake), naps, sleep debt |
| `get_whoop_weekly_trends()` | 7-day series vs 28-day baseline, HRV/RHR trend direction, acute:chronic strain ratio, overtraining flags |
| `get_whoop_full_history(refresh?)` | Your whole history summarised by month (recovery, HRV, RHR, strain, sleep, training volume per discipline). Uses the latest export, or pulls one first |
| `update_dashboard_insights(markdown_text, title?)` | Publishes markdown coaching to the dashboard's Live AI Coaching feed |
| `log_strength_session(sets, date?, notes?, link_whoop?)` | Logs sets (exercise, reps, kg, RPE, warm-up) and links them to that day's WHOOP strength workout |
| `get_strength_progress(exercise?)` | Estimated 1RM, PRs and 4-week change per lift, weekly sets per muscle, push/pull balance, performance by recovery zone, unlogged WHOOP strength workouts |
| `get_training_plan()` | This week's Half Ironman plan: phase, sessions per day, what's done, today's recovery adjustment, your usual week |
| `update_training_plan(race_date?, weekly_hours?, strength_days?, ...)` | Changes race date/name, weekly hours, gym, long and rest days |

> **Strength data.** WHOOP's API and app export have no exercise-level data (sets, reps, weights), even for
> Strength Trainer sessions. Lifts are logged in the dashboard's Strength tab or with `log_strength_session`
> and stored in `~/.whoop-mcp/strength.db`; each session links to its WHOOP workout for strain and heart rate.

> **Derived metrics.** The public WHOOP API has no Stress Monitor score, no Strain Coach target and no single
> "sleep debt" field. This server computes them and marks them with `derived: true`:
> - **Stress (0–3):** HRV suppression and RHR elevation measured against your 7-day baseline.
> - **Target strain:** a band set by your recovery zone.
> - **Rolling sleep debt:** the sum of (sleep needed − actual sleep) over the last 7 nights.
>
> WHOOP's own `need_from_sleep_debt` component is reported as well.

## Setup (Windows / PowerShell)

### 1. Register a WHOOP app
Go to <https://developer-dashboard.whoop.com>, create an app, and add the redirect URL **`http://localhost:8000/callback`**.
Select all `read:*` scopes. Copy the Client ID and Client Secret into `.env`:

```powershell
Copy-Item .env.example .env   # then edit WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET
```

### 2. Python environment
```powershell
py -m venv .venv                       # or: uv venv
.venv\Scripts\python -m pip install -e ".[dev]"   # or: uv pip install -e ".[dev]"
```

### 3. Build the dashboard (Node 18+)
```powershell
cd frontend; npm install; npm run build; cd ..
```
The build writes to `src/whoop_mcp/static/`, and FastAPI serves it from there.

### 4. Log in to WHOOP (one time)
```powershell
.venv\Scripts\python -m whoop_mcp login
```
This opens your browser for consent. The command runs a temporary server on `localhost:8000/callback`, so make sure
nothing else is using port 8000 (stop the dashboard or any running MCP session first). Tokens are saved to
`~/.whoop-mcp/whoop_tokens.json` and refreshed automatically. Check them with `python -m whoop_mcp status`.

### 5. Register with Claude Code
This project already ships a `.mcp.json`, so Claude Code picks the server up when you open this folder.
To register it for all your projects:
```powershell
claude mcp add whoop --scope user -- "C:\Users\User\Desktop\Claude-Code Apps\Whoop MCP\.venv\Scripts\python.exe" -m whoop_mcp serve
```
Credentials come from the project's `.env`, so you don't need `-e` flags. Verify with `claude mcp list`.

### 6. Dashboard
Starting the MCP server (`serve`) also starts the dashboard at **http://localhost:8000** automatically.
To run the dashboard without Claude:
```powershell
.venv\Scripts\python -m whoop_mcp dashboard
```
To see it without a WHOOP account, open **http://localhost:8000/?demo=1**.
Setting `WHOOP_MCP_DEMO=1` makes the MCP tools return demo data too.

The dashboard has four tabs:
- **Today**: live recovery, strain, sleep, 7-day trends, the workout log (7/14/28 days, strength included) and
  Claude's coaching notes.
- **Plan**: this week's Half Ironman (70.3) plan. The phase comes from the race date (base, build, peak, taper),
  sessions are placed on the days you usually train each sport, today's sessions adjust to your recovery, and
  WHOOP workouts tick sessions off. Settings: race, date, weekly hours, gym, long-ride, long-run and rest days.
- **Strength**: log full-body sessions set by set (exercises prefill from last time; Repeat last session),
  linked to the WHOOP workout. Shows e1RM progress and PRs per lift, weekly sets per muscle against a 4–12 band,
  push:pull and lower:upper, and how your lifting relates to morning recovery.
- **History**: built from the latest full-history export (below), with a 30d / 90d / 6m / All range:
  - **Training load & consistency**: weekly hours per sport, and days since your last swim, bike, run and strength session.
  - **Run intensity**: time in HR zones 1–5 per month, against an 80% easy (Z1–Z2) target.
  - **Sleep vs recovery**: every night against the next morning's recovery, average recovery by sleep length, and
    the sleep length where your recovery levels off.
  - **Calendar**: one square per day coloured by recovery, strain or sleep, with a dot on training days.
  - Recovery, HRV/RHR, strain and sleep charts, a monthly table and the full workout list.

The MCP server runs the dashboard as a reloading child process, so Python changes under `src/whoop_mcp/` take
effect on :8000 within a couple of seconds without restarting the MCP server or disconnecting its tools.
The built frontend is read from disk on every request, so after `npm run build` (or with `npm run watch`) a
browser refresh shows the new UI.

## Full-history export
```powershell
.venv\Scripts\python -m whoop_mcp export            # writes exports\<timestamp>\
```
This pulls every cycle, recovery, sleep and workout since your first day on WHOOP, plus your profile and body
measurements. Requests are throttled to stay under WHOOP's rate limit, so a multi-year account takes a few minutes.

Each export folder contains:

| File | Contents |
|---|---|
| `raw/*.json` | Untouched API records |
| `cycles.csv`, `recoveries.csv`, `sleeps.csv`, `workouts.csv` | The same records, flattened |
| `sleeps_summary.csv`, `workouts_summary.csv` | Converted to hours, minutes and km, with each workout classified as swim/bike/run |
| `monthly_summary.csv`, `manifest.json` | Monthly aggregates, record counts and date ranges |

**The WHOOP app's own export** includes journal entries that the API doesn't provide. Request it in the app under
Profile → Settings → Data Export. WHOOP emails you a ZIP. Add it to your latest export with:
```powershell
.venv\Scripts\python -m whoop_mcp import-app-export "C:\path\to\my_whoop_data.zip"
```

## Try it
> Analyze my WHOOP recovery and sleep debt today, assess if I should proceed with my planned bike threshold
> session, and update my Watermelon UI dashboard with my coaching guidance.

## Development
```powershell
.venv\Scripts\python -m pytest            # analytics, OAuth refresh, pagination/401 retry, insights store, reloader
.venv\Scripts\python -m whoop_mcp dashboard --reload   # standalone dashboard that restarts on Python changes
cd frontend; npm run dev                  # Vite on :5173 with hot module reload, proxies /api to :8000
cd frontend; npm run watch                # rebuild into src/whoop_mcp/static on every save
```

Hot reload while the MCP server owns :8000: run a second dashboard on :8001 and point Vite at it.
```powershell
$env:WHOOP_DASHBOARD_PORT=8001; .venv\Scripts\python -m whoop_mcp dashboard --reload
$env:WHOOP_API="http://localhost:8001"; cd frontend; npm run dev
```
`.claude/launch.json` has both as `whoop-dashboard-preview` and `whoop-frontend-hmr`.

### Watermelon UI
Components come from the `@watermelon` shadcn registry (`frontend/components.json`) and live in
`frontend/src/components/watermelon/`:
- `continuous-tabs`: the swim/bike/run filter.
- `activities-card`: the workout list. It has small edits: a `defaultOpen` prop and fluid width.
- `labeled-progress-indicator`: the loading state.

To add more:
`npx shadcn@latest add @watermelon/<name>`.

### Layout
```
src/whoop_mcp/
  __main__.py   CLI: login | serve | dashboard | status
  auth.py       OAuth2 consent flow, atomic token store, refresh with rotation handling
  client.py     async WHOOP v2 client: pagination, 401→refresh→retry, 429/5xx backoff
  analytics.py  pure functions: daily join, baselines, debt, stress/target-strain, trends
  service.py    fetch window + 2-min cache → reports
  server.py     FastMCP tools
  dashboard.py  FastAPI: /api/summary, /api/insights, /api/events (SSE), SPA
  insights.py   coaching feed store
  demo.py       deterministic synthetic data
frontend/       Vite + React 19 + Tailwind v4 + Radix + Motion
```
