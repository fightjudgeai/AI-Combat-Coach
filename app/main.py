"""
app/main.py — AI Combat Coach Portal

Routes:
  GET  /               Dashboard (stats, leaderboard, recent jobs)
  GET  /fighters        Fighter roster (search + filter + pagination)
  GET  /fighters/{id}   Fighter detail (FPS radar, fight history)
  GET  /scout           Scouting report (search via get_opponent_profile RPC)
  GET  /simulate        Fight simulator form
  POST /simulate        Run Monte Carlo simulation → results
  GET  /vision          Vision job queue
  GET  /vision/{id}     Vision job detail (events timeline, summary)
  POST /vision          Submit new vision job
  GET  /analytics       Aggregate charts + leaderboards

API:
  GET  /api/fighters/search?q=   Autocomplete (JSON)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Make root importable for simulation_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.simulation_engine import (
    UFCFighterVector,
    fps_delta_to_bucket,
    run_monte_carlo_simulation,
)

app = FastAPI(title="AI Combat Coach Portal", docs_url=None, redoc_url=None)

# ── Templates ─────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))


# ── Custom Jinja2 filters ─────────────────────────────────────────────────────

def _fmt_fps(v):
    try:
        return f"{float(v):.1f}" if v is not None else "—"
    except (TypeError, ValueError):
        return "—"


def _fps_tier(v):
    if v is None:
        return "UNKNOWN"
    f = float(v)
    if f >= 75:
        return "ELITE"
    if f >= 65:
        return "STRONG"
    if f >= 55:
        return "COMPETITIVE"
    if f >= 45:
        return "MIXED"
    return "POOR"


def _fps_color(v):
    if v is None:
        return "text-gray-500"
    f = float(v)
    if f >= 75:
        return "text-emerald-400"
    if f >= 65:
        return "text-green-400"
    if f >= 55:
        return "text-yellow-400"
    if f >= 45:
        return "text-orange-400"
    return "text-red-400"


def _fps_bar_color(v):
    if v is None:
        return "bg-gray-600"
    f = float(v)
    if f >= 75:
        return "bg-emerald-500"
    if f >= 65:
        return "bg-green-500"
    if f >= 55:
        return "bg-yellow-500"
    if f >= 45:
        return "bg-orange-500"
    return "bg-red-500"


def _archetype_style(archetype: str | None) -> str:
    mapping = {
        "striker":          "bg-red-500/15 text-red-400 border-red-500/25",
        "grappler":         "bg-blue-500/15 text-blue-400 border-blue-500/25",
        "wrestler":         "bg-purple-500/15 text-purple-400 border-purple-500/25",
        "balanced":         "bg-gray-500/15 text-gray-400 border-gray-500/25",
        "submission_artist":"bg-cyan-500/15 text-cyan-400 border-cyan-500/25",
        "pressure_fighter": "bg-orange-500/15 text-orange-400 border-orange-500/25",
        "counter_striker":  "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
        "kickboxer":        "bg-pink-500/15 text-pink-400 border-pink-500/25",
    }
    return mapping.get((archetype or "").lower(), "bg-gray-500/15 text-gray-400 border-gray-500/25")


def _pct(v):
    try:
        return f"{float(v) * 100:.0f}%" if v is not None else "—"
    except (TypeError, ValueError):
        return "—"


def _status_style(status: str) -> str:
    return {
        "pending": "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
        "running": "bg-blue-500/15 text-blue-400 border-blue-500/25",
        "done":    "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
        "error":   "bg-red-500/15 text-red-400 border-red-500/25",
    }.get(status, "bg-gray-500/15 text-gray-400 border-gray-500/25")


templates.env.filters["fmt_fps"] = _fmt_fps
templates.env.filters["fps_tier"] = _fps_tier
templates.env.filters["fps_color"] = _fps_color
templates.env.filters["fps_bar_color"] = _fps_bar_color
templates.env.filters["archetype_style"] = _archetype_style
templates.env.filters["pct"] = _pct
templates.env.filters["status_style"] = _status_style


# ── Supabase client ───────────────────────────────────────────────────────────

def _get_db():
    url = os.environ.get("SUPABASE_URL", "")
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _safe(fn, default=None):
    """Run fn(), returning default on any exception."""
    try:
        return fn()
    except Exception:
        return default


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = _get_db()
    stats = {"fighters": 0, "jobs": 0, "fights": 0, "scraped": 0}
    top_fighters: list = []
    recent_jobs: list = []

    if db:
        r = _safe(lambda: db.table("ufc_fighters")
                  .select("id", count="exact")
                  .eq("meets_5_fight_threshold", True)
                  .execute())
        if r:
            stats["fighters"] = r.count or 0

        r = _safe(lambda: db.table("vision_jobs")
                  .select("id", count="exact").execute())
        if r:
            stats["jobs"] = r.count or 0

        r = _safe(lambda: db.table("ufc_fights")
                  .select("id", count="exact").execute())
        if r:
            stats["fights"] = r.count or 0

        r = _safe(lambda: db.table("scraped_fighters")
                  .select("id", count="exact").execute())
        if r:
            stats["scraped"] = r.count or 0

        r = _safe(lambda: db.table("ufc_fighters")
                  .select("id,name,career_fps,style_archetype,weight_class,ufc_appearances,ufc_wins,ufc_losses,ufc_draws,finish_rate")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("career_fps", "null")
                  .order("career_fps", desc=True)
                  .limit(10)
                  .execute())
        if r:
            top_fighters = r.data or []

        r = _safe(lambda: db.table("vision_jobs")
                  .select("id,video_source,source_type,status,frames_sampled,created_at,updated_at,error_msg")
                  .order("created_at", desc=True)
                  .limit(6)
                  .execute())
        if r:
            recent_jobs = r.data or []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "top_fighters": top_fighters,
        "recent_jobs": recent_jobs,
        "db_connected": db is not None,
        "page_title": "Dashboard",
    })


# ── Fighters list ─────────────────────────────────────────────────────────────

_WEIGHT_CLASSES = [
    "Strawweight", "Flyweight", "Bantamweight", "Featherweight",
    "Lightweight", "Welterweight", "Middleweight", "Light Heavyweight",
    "Heavyweight", "Women's Strawweight", "Women's Flyweight",
    "Women's Bantamweight", "Women's Featherweight",
]
_ARCHETYPES = [
    "striker", "grappler", "wrestler", "balanced",
    "submission_artist", "pressure_fighter", "counter_striker", "kickboxer",
]
_TIERS = ["DOMINANT", "STRONG", "COMPETITIVE", "MIXED", "LOSING", "POOR"]

_PER_PAGE = 24


@app.get("/fighters", response_class=HTMLResponse)
async def fighters_list(
    request: Request,
    q: str = "",
    weight_class: str = "",
    archetype: str = "",
    tier: str = "",
    page: int = 1,
):
    db = _get_db()
    fighters: list = []
    total = 0

    if db:
        def _query():
            qb = (
                db.table("ufc_fighters")
                .select(
                    "id,name,career_fps,career_fps_tier,style_archetype,style_tags,"
                    "weight_class,ufc_wins,ufc_losses,ufc_draws,ufc_appearances,finish_rate,ko_rate,sub_rate",
                    count="exact",
                )
                .eq("meets_5_fight_threshold", True)
                .not_.is_("career_fps", "null")
            )
            if q:
                qb = qb.ilike("name", f"%{q}%")
            if weight_class:
                qb = qb.ilike("weight_class", f"%{weight_class}%")
            if archetype:
                qb = qb.eq("style_archetype", archetype)
            if tier:
                qb = qb.eq("career_fps_tier", tier)
            offset = (page - 1) * _PER_PAGE
            return qb.order("career_fps", desc=True).range(offset, offset + _PER_PAGE - 1).execute()

        r = _safe(_query)
        if r:
            fighters = r.data or []
            total = r.count or 0

    total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)

    return templates.TemplateResponse("fighters.html", {
        "request": request,
        "fighters": fighters,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "weight_class": weight_class,
        "archetype": archetype,
        "tier": tier,
        "weight_classes": _WEIGHT_CLASSES,
        "archetypes": _ARCHETYPES,
        "tiers": _TIERS,
        "db_connected": db is not None,
        "page_title": "Fighters",
    })


# ── Fighter detail ────────────────────────────────────────────────────────────

@app.get("/fighters/{fighter_id}", response_class=HTMLResponse)
async def fighter_detail(request: Request, fighter_id: str):
    db = _get_db()
    fighter = None
    fights: list = []
    fps_components: dict = {}

    if db:
        r = _safe(lambda: db.table("ufc_fighters").select("*").eq("id", fighter_id).maybe_single().execute())
        if r:
            fighter = r.data

    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")

    if db:
        r = _safe(lambda: db.table("ufc_fights")
                  .select(
                      "id,event_name,fight_date,fighter_a_name,fighter_b_name,"
                      "winner_name,method,method_normalized,finish_round,rounds_scheduled,"
                      "fighter_a_fps,fighter_b_fps,fighter_a_id,is_title_fight,is_main_event"
                  )
                  .or_(f"fighter_a_id.eq.{fighter_id},fighter_b_id.eq.{fighter_id}")
                  .order("fight_date", desc=True)
                  .limit(12)
                  .execute())
        if r:
            fights = r.data or []

    fps_components = {
        "Offensive Eff.":   float(fighter.get("avg_offensive_efficiency") or 0),
        "Defensive Resp.":  float(fighter.get("avg_defensive_response") or 0),
        "Control":          float(fighter.get("avg_control_dictation") or 0),
        "Finish Threat":    float(fighter.get("avg_finish_threat") or 0),
        "Cardio & Pace":    float(fighter.get("avg_cardio_pace") or 0),
        "Durability":       float(fighter.get("avg_durability") or 0),
        "Fight IQ":         float(fighter.get("avg_fight_iq") or 0),
        "Dominance":        float(fighter.get("avg_dominance") or 0),
    }

    return templates.TemplateResponse("fighter_detail.html", {
        "request": request,
        "fighter": fighter,
        "fights": fights,
        "fps_components_json": json.dumps(fps_components),
        "fps_components": fps_components,
        "page_title": fighter["name"],
    })


# ── Scout ─────────────────────────────────────────────────────────────────────

@app.get("/scout", response_class=HTMLResponse)
async def scout(request: Request, q: str = ""):
    db = _get_db()
    profile = None
    error: str | None = None

    if q and db:
        # Use DB function get_opponent_profile first
        r = _safe(lambda: db.rpc("get_opponent_profile", {"p_fighter_name": q}).execute())
        if r and r.data:
            profile = r.data
        else:
            # Fallback: search ufc_fighters directly
            r2 = _safe(lambda: db.table("ufc_fighters")
                        .select("*")
                        .ilike("name", f"%{q}%")
                        .eq("meets_5_fight_threshold", True)
                        .order("ufc_appearances", desc=True)
                        .limit(1)
                        .execute())
            if r2 and r2.data:
                uf = r2.data[0]
                fid = uf["id"]
                # recent fights
                rfr = _safe(lambda: db.table("ufc_fights")
                             .select("event_name,fight_date,fighter_a_name,fighter_b_name,winner_name,method,fighter_a_id")
                             .or_(f"fighter_a_id.eq.{fid},fighter_b_id.eq.{fid}")
                             .order("fight_date", desc=True)
                             .limit(5)
                             .execute())
                recent = []
                if rfr and rfr.data:
                    for f in rfr.data:
                        is_a = str(f.get("fighter_a_id")) == str(fid)
                        opp = f["fighter_b_name"] if is_a else f["fighter_a_name"]
                        won = f.get("winner_name") == uf["name"]
                        recent.append({
                            "result": "W" if won else "L",
                            "method": f.get("method", ""),
                            "opponent_name": opp,
                            "event_name": f.get("event_name", ""),
                            "event_date": f.get("fight_date", ""),
                        })
                profile = {
                    "source": "ufc_fighters",
                    "name": uf["name"],
                    "weight_class": uf.get("weight_class"),
                    "fps": uf.get("career_fps"),
                    "fps_tier": uf.get("career_fps_tier"),
                    "record": {
                        "wins": uf.get("ufc_wins", 0),
                        "losses": uf.get("ufc_losses", 0),
                        "draws": uf.get("ufc_draws", 0),
                        "finish_rate": uf.get("finish_rate"),
                        "ko_rate": uf.get("ko_rate"),
                        "sub_rate": uf.get("sub_rate"),
                    },
                    "style": uf.get("style_archetype"),
                    "style_tags": uf.get("style_tags") or [],
                    "ufc_appearances": uf.get("ufc_appearances"),
                    "recent_fights": recent,
                }
            else:
                error = f'No fighter found matching "{q}"'

    return templates.TemplateResponse("scout.html", {
        "request": request,
        "q": q,
        "profile": profile,
        "error": error,
        "db_connected": db is not None,
        "page_title": "Scout",
    })


# ── Simulator ─────────────────────────────────────────────────────────────────

@app.get("/simulate", response_class=HTMLResponse)
async def simulate_get(request: Request):
    return templates.TemplateResponse("simulator.html", {
        "request": request,
        "result": None,
        "result_json": "null",
        "error": None,
        "fighter_a_name": "",
        "fighter_b_name": "",
        "rounds": 3,
        "page_title": "Fight Simulator",
    })


@app.post("/simulate", response_class=HTMLResponse)
async def simulate_post(
    request: Request,
    fighter_a: str = Form(...),
    fighter_b: str = Form(...),
    rounds: int = Form(3),
):
    db = _get_db()
    result = None
    error: str | None = None
    fa_data = fb_data = None

    if not db:
        error = "Database not connected. Set SUPABASE_URL and SUPABASE_SERVICE_KEY."
    else:
        def _fetch(name: str):
            return (
                db.table("ufc_fighters")
                .select("*")
                .ilike("name", f"%{name}%")
                .eq("meets_5_fight_threshold", True)
                .not_.is_("career_fps", "null")
                .order("ufc_appearances", desc=True)
                .limit(1)
                .execute()
            )

        ra = _safe(lambda: _fetch(fighter_a))
        if not ra or not ra.data:
            error = f'"{fighter_a}" not found — needs 5+ UFC fights with FPS data.'
        else:
            fa_data = ra.data[0]
            rb = _safe(lambda: _fetch(fighter_b))
            if not rb or not rb.data:
                error = f'"{fighter_b}" not found — needs 5+ UFC fights with FPS data.'
            else:
                fb_data = rb.data[0]

                def _vec(d: dict) -> UFCFighterVector:
                    return UFCFighterVector(
                        fighter_id=str(d["id"]),
                        name=d["name"],
                        career_fps=float(d["career_fps"]),
                        style_archetype=d.get("style_archetype") or "balanced",
                        style_tags=d.get("style_tags") or [],
                        offensive_efficiency=float(d.get("avg_offensive_efficiency") or 55),
                        defensive_response=float(d.get("avg_defensive_response") or 55),
                        control_dictation=float(d.get("avg_control_dictation") or 55),
                        finish_threat=float(d.get("avg_finish_threat") or 55),
                        cardio_pace=float(d.get("avg_cardio_pace") or 55),
                        durability=float(d.get("avg_durability") or 60),
                        fight_iq=float(d.get("avg_fight_iq") or 55),
                        dominance=float(d.get("avg_dominance") or 50),
                    )

                prob_tables: dict = {}
                style_mods: dict = {}
                rp = _safe(lambda: db.table("system_config")
                            .select("value")
                            .eq("key", "simulation_probability_tables")
                            .maybe_single()
                            .execute())
                if rp and rp.data:
                    prob_tables = rp.data.get("value") or {}

                rs = _safe(lambda: db.table("system_config")
                            .select("value")
                            .eq("key", "style_modifiers")
                            .maybe_single()
                            .execute())
                if rs and rs.data:
                    payload = rs.data.get("value") or {}
                    style_mods = payload.get("pairings", {}) if isinstance(payload, dict) else {}

                try:
                    vec_a, vec_b = _vec(fa_data), _vec(fb_data)
                    result = run_monte_carlo_simulation(
                        vec_a, vec_b, rounds, prob_tables, style_mods, n_simulations=10_000
                    )
                    result.update({
                        "fighter_a_name": fa_data["name"],
                        "fighter_b_name": fb_data["name"],
                        "fighter_a_fps": float(fa_data["career_fps"]),
                        "fighter_b_fps": float(fb_data["career_fps"]),
                        "fighter_a_archetype": fa_data.get("style_archetype") or "balanced",
                        "fighter_b_archetype": fb_data.get("style_archetype") or "balanced",
                        "fighter_a_record": f"{fa_data['ufc_wins']}-{fa_data['ufc_losses']}-{fa_data['ufc_draws']}",
                        "fighter_b_record": f"{fb_data['ufc_wins']}-{fb_data['ufc_losses']}-{fb_data['ufc_draws']}",
                        "rounds_scheduled": rounds,
                    })
                except Exception as exc:
                    error = f"Simulation error: {exc}"

    return templates.TemplateResponse("simulator.html", {
        "request": request,
        "result": result,
        "result_json": json.dumps(result) if result else "null",
        "error": error,
        "fighter_a_name": fa_data["name"] if fa_data else fighter_a,
        "fighter_b_name": fb_data["name"] if fb_data else fighter_b,
        "rounds": rounds,
        "fa_data": fa_data,
        "fb_data": fb_data,
        "page_title": "Fight Simulator",
    })


# ── Vision jobs ───────────────────────────────────────────────────────────────

@app.get("/vision", response_class=HTMLResponse)
async def vision_list(
    request: Request,
    status: str = "",
    page: int = 1,
):
    db = _get_db()
    jobs: list = []
    total = 0
    per_page = 20

    if db:
        def _q():
            qb = db.table("vision_jobs").select(
                "id,video_source,source_type,status,frames_sampled,"
                "duration_secs,created_at,updated_at,fighter_id,error_msg",
                count="exact",
            )
            if status:
                qb = qb.eq("status", status)
            offset = (page - 1) * per_page
            return qb.order("created_at", desc=True).range(offset, offset + per_page - 1).execute()

        r = _safe(_q)
        if r:
            jobs = r.data or []
            total = r.count or 0

    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse("vision.html", {
        "request": request,
        "jobs": jobs,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status_filter": status,
        "db_connected": db is not None,
        "page_title": "Vision Jobs",
    })


@app.get("/vision/{job_id}", response_class=HTMLResponse)
async def vision_detail(request: Request, job_id: str):
    db = _get_db()
    job = None
    events: list = []
    summary = None

    if db:
        r = _safe(lambda: db.table("vision_jobs").select("*").eq("id", job_id).maybe_single().execute())
        if r:
            job = r.data

    if not job:
        raise HTTPException(status_code=404, detail="Vision job not found")

    if db:
        r = _safe(lambda: db.table("fight_events")
                  .select("id,timestamp_secs,event_type,limb,target_zone,outcome,position,confidence")
                  .eq("job_id", job_id)
                  .order("timestamp_secs")
                  .limit(500)
                  .execute())
        if r:
            events = r.data or []

        r = _safe(lambda: db.table("fight_event_summary")
                  .select("*")
                  .eq("job_id", job_id)
                  .limit(2)
                  .execute())
        if r and r.data:
            summary = r.data[0]

    return templates.TemplateResponse("vision_detail.html", {
        "request": request,
        "job": job,
        "events": events,
        "summary": summary,
        "page_title": f"Job {job_id[:8]}…",
    })


@app.post("/vision")
async def vision_submit(
    request: Request,
    video_source: str = Form(...),
    fighter_id: str = Form(""),
):
    db = _get_db()
    if not db:
        return RedirectResponse("/vision?error=no_db", status_code=303)

    src = video_source.strip()
    source_type = (
        "youtube" if ("youtube.com" in src or "youtu.be" in src) else
        "s3" if src.startswith("s3://") else
        "local"
    )

    row: dict = {"video_source": src, "source_type": source_type, "status": "pending"}
    if fighter_id.strip():
        row["fighter_id"] = fighter_id.strip()

    r = _safe(lambda: db.table("vision_jobs").insert(row).execute())
    if r and r.data:
        job_id = r.data[0]["id"]
        return RedirectResponse(f"/vision/{job_id}", status_code=303)

    return RedirectResponse("/vision", status_code=303)


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    db = _get_db()
    archetype_dist: list = []
    weight_class_dist: list = []
    fps_tier_dist: list = []
    method_dist: list = []
    top_finishers: list = []
    leaderboard: list = []

    if db:
        r = _safe(lambda: db.table("ufc_fighters")
                  .select("style_archetype")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("style_archetype", "null")
                  .execute())
        if r and r.data:
            cnt = Counter(f["style_archetype"] for f in r.data if f.get("style_archetype"))
            archetype_dist = [{"label": k, "count": v} for k, v in cnt.most_common()]

        r = _safe(lambda: db.table("ufc_fighters")
                  .select("weight_class")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("weight_class", "null")
                  .execute())
        if r and r.data:
            cnt = Counter(f["weight_class"] for f in r.data if f.get("weight_class"))
            weight_class_dist = [{"label": k, "count": v} for k, v in cnt.most_common(12)]

        r = _safe(lambda: db.table("ufc_fighters")
                  .select("career_fps_tier")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("career_fps_tier", "null")
                  .execute())
        if r and r.data:
            cnt = Counter(f["career_fps_tier"] for f in r.data if f.get("career_fps_tier"))
            fps_tier_dist = [{"label": k, "count": v} for k, v in cnt.most_common()]

        r = _safe(lambda: db.table("ufc_fights")
                  .select("method_normalized")
                  .not_.is_("method_normalized", "null")
                  .execute())
        if r and r.data:
            cnt = Counter(f["method_normalized"] for f in r.data if f.get("method_normalized"))
            method_dist = [{"label": k, "count": v} for k, v in cnt.most_common()]

        r = _safe(lambda: db.table("ufc_fighters")
                  .select("name,career_fps,style_archetype,finish_rate,ko_rate,sub_rate,ufc_appearances,weight_class")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("finish_rate", "null")
                  .order("finish_rate", desc=True)
                  .limit(10)
                  .execute())
        if r:
            top_finishers = r.data or []

        r = _safe(lambda: db.table("ufc_fighters")
                  .select("id,name,career_fps,career_fps_tier,style_archetype,weight_class,ufc_wins,ufc_losses,ufc_appearances")
                  .eq("meets_5_fight_threshold", True)
                  .not_.is_("career_fps", "null")
                  .order("career_fps", desc=True)
                  .limit(25)
                  .execute())
        if r:
            leaderboard = r.data or []

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "archetype_dist_json": json.dumps(archetype_dist),
        "weight_class_dist_json": json.dumps(weight_class_dist),
        "fps_tier_dist_json": json.dumps(fps_tier_dist),
        "method_dist_json": json.dumps(method_dist),
        "top_finishers": top_finishers,
        "leaderboard": leaderboard,
        "db_connected": db is not None,
        "page_title": "Analytics",
    })


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/fighters/search")
async def api_fighter_search(q: str = "", limit: int = 8):
    if not q or len(q) < 2:
        return JSONResponse([])
    db = _get_db()
    if not db:
        return JSONResponse([])
    r = _safe(lambda: db.table("ufc_fighters")
              .select("id,name,career_fps,style_archetype,weight_class")
              .ilike("name", f"%{q}%")
              .eq("meets_5_fight_threshold", True)
              .not_.is_("career_fps", "null")
              .order("ufc_appearances", desc=True)
              .limit(limit)
              .execute())
    return JSONResponse(r.data if r else [])


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request, "page_title": "404"}, status_code=404)
