from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import uuid
import secrets
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import List, Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Password helpers ──
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def get_jwt_secret():
    return os.environ["JWT_SECRET"]

def create_access_token(user_id: str, email: str) -> str:
    return jwt.encode({"sub": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(minutes=60), "type": "access"}, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def serialize_doc(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc

# ── Pydantic Models ──
class RegisterInput(BaseModel):
    email: str
    password: str
    name: str
    role: str = "staff"

class LoginInput(BaseModel):
    email: str
    password: str

class EventInput(BaseModel):
    title: str
    date: str
    venue: str
    city: str = ""
    status: str = "planning"
    description: str = ""
    budget: float = 0
    ticket_price: float = 0
    capacity: int = 0

class FighterInput(BaseModel):
    name: str
    nickname: str = ""
    weight_class: str
    wins: int = 0
    losses: int = 0
    draws: int = 0
    status: str = "active"
    age: int = 0
    height: str = ""
    reach: str = ""
    stance: str = "orthodox"
    gym: str = ""

class BoutInput(BaseModel):
    event_id: str
    fighter1_id: str
    fighter2_id: str
    weight_class: str
    rounds: int = 3
    is_main_event: bool = False
    bout_order: int = 0

class TaskInput(BaseModel):
    title: str
    description: str = ""
    event_id: Optional[str] = None
    due_date: str = ""
    priority: str = "medium"
    status: str = "pending"
    recurrence: str = "none"
    assigned_to: Optional[str] = None

class FinancialInput(BaseModel):
    event_id: str
    type: str
    category: str
    amount: float
    description: str = ""

class AIPromoInput(BaseModel):
    event_title: str
    event_date: str
    venue: str
    main_event: str = ""
    style: str = "hype"

class AIMatchupInput(BaseModel):
    weight_class: str
    event_id: Optional[str] = None

# ── Auth Endpoints ──
@api_router.post("/auth/register")
async def register(input: RegisterInput, response: Response):
    email = input.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = {
        "email": email,
        "password_hash": hash_password(input.password),
        "name": input.name,
        "role": input.role if input.role in ["admin", "staff", "matchmaker"] else "staff",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {"id": user_id, "email": email, "name": input.name, "role": user_doc["role"]}

@api_router.post("/auth/login")
async def login(input: LoginInput, request: Request, response: Response):
    email = input.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.now(timezone.utc) < datetime.fromisoformat(locked_until):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(input.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    user_id = str(user["_id"])
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    return {"id": user_id, "email": email, "name": user.get("name", ""), "role": user.get("role", "staff")}

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = str(user["_id"])
        access = create_access_token(user_id, user["email"])
        response.set_cookie(key="access_token", value=access, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
        return {"message": "Token refreshed"}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

# ── Events ──
@api_router.get("/events")
async def list_events(user: dict = Depends(get_current_user)):
    events = await db.events.find({}, {"_id": 1}).to_list(500)
    result = []
    async for ev in db.events.find({}):
        result.append(serialize_doc(ev))
    return result

@api_router.post("/events")
async def create_event(input: EventInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["created_by"] = user["_id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.events.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

@api_router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(get_current_user)):
    ev = await db.events.find_one({"_id": ObjectId(event_id)})
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return serialize_doc(ev)

@api_router.put("/events/{event_id}")
async def update_event(event_id: str, input: EventInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.events.update_one({"_id": ObjectId(event_id)}, {"$set": doc})
    ev = await db.events.find_one({"_id": ObjectId(event_id)})
    return serialize_doc(ev)

@api_router.delete("/events/{event_id}")
async def delete_event(event_id: str, user: dict = Depends(get_current_user)):
    await db.events.delete_one({"_id": ObjectId(event_id)})
    return {"message": "Event deleted"}

# ── Fighters ──
@api_router.get("/fighters")
async def list_fighters(user: dict = Depends(get_current_user)):
    result = []
    async for f in db.fighters.find({}):
        result.append(serialize_doc(f))
    return result

@api_router.post("/fighters")
async def create_fighter(input: FighterInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["created_by"] = user["_id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.fighters.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

@api_router.get("/fighters/{fighter_id}")
async def get_fighter(fighter_id: str, user: dict = Depends(get_current_user)):
    f = await db.fighters.find_one({"_id": ObjectId(fighter_id)})
    if not f:
        raise HTTPException(status_code=404, detail="Fighter not found")
    return serialize_doc(f)

@api_router.put("/fighters/{fighter_id}")
async def update_fighter(fighter_id: str, input: FighterInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.fighters.update_one({"_id": ObjectId(fighter_id)}, {"$set": doc})
    f = await db.fighters.find_one({"_id": ObjectId(fighter_id)})
    return serialize_doc(f)

@api_router.delete("/fighters/{fighter_id}")
async def delete_fighter(fighter_id: str, user: dict = Depends(get_current_user)):
    await db.fighters.delete_one({"_id": ObjectId(fighter_id)})
    return {"message": "Fighter deleted"}

# ── Bouts / Fight Card ──
@api_router.get("/bouts")
async def list_bouts(event_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {"event_id": event_id} if event_id else {}
    result = []
    async for b in db.bouts.find(query).sort("bout_order", 1):
        bout = serialize_doc(b)
        # Populate fighter names
        for key in ["fighter1_id", "fighter2_id"]:
            try:
                fighter = await db.fighters.find_one({"_id": ObjectId(bout[key])})
                if fighter:
                    bout[key.replace("_id", "_name")] = fighter.get("name", "Unknown")
                    bout[key.replace("_id", "_nickname")] = fighter.get("nickname", "")
                    bout[key.replace("_id", "_record")] = f"{fighter.get('wins',0)}-{fighter.get('losses',0)}-{fighter.get('draws',0)}"
            except Exception:
                pass
        result.append(bout)
    return result

@api_router.post("/bouts")
async def create_bout(input: BoutInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["result"] = ""
    doc["status"] = "scheduled"
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.bouts.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

@api_router.put("/bouts/{bout_id}")
async def update_bout(bout_id: str, input: BoutInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    await db.bouts.update_one({"_id": ObjectId(bout_id)}, {"$set": doc})
    b = await db.bouts.find_one({"_id": ObjectId(bout_id)})
    return serialize_doc(b)

@api_router.delete("/bouts/{bout_id}")
async def delete_bout(bout_id: str, user: dict = Depends(get_current_user)):
    await db.bouts.delete_one({"_id": ObjectId(bout_id)})
    return {"message": "Bout deleted"}

# ── Tasks ──
@api_router.get("/tasks")
async def list_tasks(event_id: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {}
    if event_id:
        query["event_id"] = event_id
    if status:
        query["status"] = status
    result = []
    async for t in db.tasks.find(query).sort("due_date", 1):
        result.append(serialize_doc(t))
    return result

@api_router.post("/tasks")
async def create_task(input: TaskInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["created_by"] = user["_id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.tasks.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

@api_router.put("/tasks/{task_id}")
async def update_task(task_id: str, input: TaskInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": doc})
    t = await db.tasks.find_one({"_id": ObjectId(task_id)})
    return serialize_doc(t)

@api_router.patch("/tasks/{task_id}/status")
async def toggle_task_status(task_id: str, user: dict = Depends(get_current_user)):
    t = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    new_status = "completed" if t.get("status") != "completed" else "pending"
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}})
    t = await db.tasks.find_one({"_id": ObjectId(task_id)})
    return serialize_doc(t)

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    await db.tasks.delete_one({"_id": ObjectId(task_id)})
    return {"message": "Task deleted"}

# ── Financials ──
@api_router.get("/financials")
async def list_financials(event_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    query = {"event_id": event_id} if event_id else {}
    result = []
    async for f in db.financials.find(query):
        result.append(serialize_doc(f))
    return result

@api_router.post("/financials")
async def create_financial(input: FinancialInput, user: dict = Depends(get_current_user)):
    doc = input.model_dump()
    doc["created_by"] = user["_id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.financials.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return doc

@api_router.delete("/financials/{fin_id}")
async def delete_financial(fin_id: str, user: dict = Depends(get_current_user)):
    await db.financials.delete_one({"_id": ObjectId(fin_id)})
    return {"message": "Record deleted"}

@api_router.get("/financials/summary")
async def financial_summary(user: dict = Depends(get_current_user)):
    revenue = 0
    expenses = 0
    async for f in db.financials.find({}):
        if f.get("type") == "revenue":
            revenue += f.get("amount", 0)
        else:
            expenses += f.get("amount", 0)
    return {"total_revenue": revenue, "total_expenses": expenses, "net": revenue - expenses}

# ── Dashboard Stats ──
@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    events_count = await db.events.count_documents({})
    fighters_count = await db.fighters.count_documents({})
    upcoming = await db.events.count_documents({"status": {"$in": ["planning", "announced", "confirmed"]}})
    tasks_pending = await db.tasks.count_documents({"status": "pending"})
    tasks_completed = await db.tasks.count_documents({"status": "completed"})
    revenue = 0
    expenses = 0
    async for f in db.financials.find({}):
        if f.get("type") == "revenue":
            revenue += f.get("amount", 0)
        else:
            expenses += f.get("amount", 0)
    recent_events = []
    async for ev in db.events.find({}).sort("created_at", -1).limit(5):
        recent_events.append(serialize_doc(ev))
    return {
        "total_events": events_count,
        "total_fighters": fighters_count,
        "upcoming_events": upcoming,
        "tasks_pending": tasks_pending,
        "tasks_completed": tasks_completed,
        "total_revenue": revenue,
        "total_expenses": expenses,
        "net_profit": revenue - expenses,
        "recent_events": recent_events
    }

# ── AI Endpoints ──
@api_router.post("/ai/generate-promo")
async def generate_promo(input: AIPromoInput, user: dict = Depends(get_current_user)):
    try:
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"promo-{uuid.uuid4()}",
            system_message="You are a combat sports event promoter copywriter. Write compelling, hype promotional descriptions for MMA/boxing events. Keep it under 200 words. Be dramatic and exciting."
        )
        prompt = f"Write a promotional description for this combat sports event:\nEvent: {input.event_title}\nDate: {input.event_date}\nVenue: {input.venue}\nMain Event: {input.main_event}\nStyle: {input.style}"
        msg = UserMessage(text=prompt)
        result = await chat.send_message(msg)
        return {"promo_text": result}
    except Exception as e:
        logger.error(f"AI promo generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate promo text")

@api_router.post("/ai/matchup-suggestions")
async def matchup_suggestions(input: AIMatchupInput, user: dict = Depends(get_current_user)):
    try:
        fighters = []
        async for f in db.fighters.find({"weight_class": input.weight_class, "status": "active"}):
            fighters.append({"name": f["name"], "nickname": f.get("nickname", ""), "record": f"{f.get('wins',0)}-{f.get('losses',0)}-{f.get('draws',0)}", "id": str(f["_id"])})
        if len(fighters) < 2:
            return {"suggestions": [], "message": "Need at least 2 active fighters in this weight class"}
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"matchup-{uuid.uuid4()}",
            system_message="You are an expert MMA/boxing matchmaker. Suggest compelling fight matchups based on fighter records and styles. Return JSON array of matchups with reasoning."
        )
        fighter_list = "\n".join([f"- {f['name']} ({f['nickname']}) Record: {f['record']}" for f in fighters])
        prompt = f"Given these {input.weight_class} fighters, suggest the top 3 most compelling matchups:\n{fighter_list}\n\nReturn a JSON array with objects containing: fighter1, fighter2, reasoning"
        msg = UserMessage(text=prompt)
        result = await chat.send_message(msg)
        return {"suggestions": result, "fighters_count": len(fighters)}
    except Exception as e:
        logger.error(f"AI matchup suggestion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate matchup suggestions")

# ── Users (for role management) ──
@api_router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    result = []
    async for u in db.users.find({}, {"password_hash": 0}):
        result.append(serialize_doc(u))
    return result

# ── App Setup ──
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@fightpromo.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
        logger.info("Admin password updated")

    # Seed sample data
    if await db.fighters.count_documents({}) == 0:
        sample_fighters = [
            {"name": "Marcus 'The Hammer' Johnson", "nickname": "The Hammer", "weight_class": "Welterweight", "wins": 12, "losses": 3, "draws": 0, "status": "active", "age": 28, "height": "5'11\"", "reach": "74\"", "stance": "orthodox", "gym": "Iron Forge MMA", "created_at": datetime.now(timezone.utc).isoformat()},
            {"name": "Diego 'El Toro' Ramirez", "nickname": "El Toro", "weight_class": "Welterweight", "wins": 15, "losses": 2, "draws": 1, "status": "active", "age": 31, "height": "5'10\"", "reach": "72\"", "stance": "southpaw", "gym": "Ramirez Combat", "created_at": datetime.now(timezone.utc).isoformat()},
            {"name": "Kai 'Thunder' Nakamura", "nickname": "Thunder", "weight_class": "Lightweight", "wins": 18, "losses": 1, "draws": 0, "status": "active", "age": 26, "height": "5'8\"", "reach": "70\"", "stance": "orthodox", "gym": "Tokyo Fight Lab", "created_at": datetime.now(timezone.utc).isoformat()},
            {"name": "Amir 'The Lion' Hassan", "nickname": "The Lion", "weight_class": "Lightweight", "wins": 10, "losses": 4, "draws": 0, "status": "active", "age": 29, "height": "5'9\"", "reach": "71\"", "stance": "orthodox", "gym": "Lion's Den", "created_at": datetime.now(timezone.utc).isoformat()},
            {"name": "Tommy 'Bones' O'Brien", "nickname": "Bones", "weight_class": "Middleweight", "wins": 20, "losses": 5, "draws": 2, "status": "active", "age": 33, "height": "6'1\"", "reach": "76\"", "stance": "orthodox", "gym": "Celtic Warriors", "created_at": datetime.now(timezone.utc).isoformat()},
            {"name": "Sergei 'The Tank' Volkov", "nickname": "The Tank", "weight_class": "Heavyweight", "wins": 14, "losses": 3, "draws": 0, "status": "active", "age": 30, "height": "6'4\"", "reach": "80\"", "stance": "orthodox", "gym": "Ural Combat Club", "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.fighters.insert_many(sample_fighters)
        logger.info("Sample fighters seeded")

    if await db.events.count_documents({}) == 0:
        sample_events = [
            {"title": "FURY FC 12: REDEMPTION", "date": "2026-03-15", "venue": "Madison Square Garden", "city": "New York", "status": "confirmed", "description": "The biggest fight card of the year", "budget": 250000, "ticket_price": 85, "capacity": 5000, "created_at": datetime.now(timezone.utc).isoformat()},
            {"title": "BATTLEGROUND 8: RISE", "date": "2026-04-22", "venue": "T-Mobile Arena", "city": "Las Vegas", "status": "planning", "description": "Rising stars clash", "budget": 180000, "ticket_price": 65, "capacity": 3500, "created_at": datetime.now(timezone.utc).isoformat()},
            {"title": "IRON CAGE CHAMPIONSHIP", "date": "2026-06-10", "venue": "O2 Arena", "city": "London", "status": "announced", "description": "International championship bout", "budget": 320000, "ticket_price": 120, "capacity": 8000, "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.events.insert_many(sample_events)
        logger.info("Sample events seeded")

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")

    # Write test credentials
    cred_path = Path("/app/memory/test_credentials.md")
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    cred_path.write_text(f"""# Test Credentials

## Admin Account
- Email: {admin_email}
- Password: {admin_password}
- Role: admin

## Auth Endpoints
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/auth/me
- POST /api/auth/refresh
""")

@app.on_event("startup")
async def startup():
    await seed_admin()

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
