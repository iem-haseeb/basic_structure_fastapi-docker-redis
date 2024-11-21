
from datetime import datetime, timedelta, timezone, date, time
import redis
import jwt
import time as t
from passlib.context import CryptContext
from typing import Annotated
from fastapi import Form, Depends,  FastAPI, Request,HTTPException,status, Cookie
from fastapi.templating import Jinja2Templates
import json
from sqlmodel import Field, Session, SQLModel, create_engine
from sqlalchemy import ForeignKey
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv

import logging
log = logging.getLogger(__name__)

class User(SQLModel, table=True):
    name: str = Field(index=False)
    email: str | None = Field(default=None,primary_key=True)
    password: str = Field(index=True)

class Task(SQLModel, table=True):
    task_date: date= Field(default=None)
    task_time: time = Field(default=None)
    task_name: str = Field(default=None, primary_key=True)
    email: str = Field(ForeignKey('User.email', ondelete='CASCADE'), index=True)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
load_dotenv()
SECRET_KEY =os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 300
sqlite_file_name = os.getenv("sqlite_file_name")
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)
templates = Jinja2Templates(directory="templates")
r = redis.Redis(host="redis", port=6379, db=0)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]



@app.on_event("startup")
def on_startup():
    create_db_and_tables()

async def log_request_middleware(request: Request, call_next):
    request_start_time = t.monotonic()
    response = await call_next(request)
    request_duration = t.monotonic() - request_start_time
    print("middleware is used")
    log_data = {
        "method": request.method,
        "path": request.url.path,
        "duration": request_duration
    }
    log.info(log_data)
    return response

app.middleware("http")(log_request_middleware)
@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_active_user(token: Annotated[str, Depends(oauth2_scheme)],session: Session = Depends(get_session)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    email = payload.get("email")
    user = session.query(User).filter_by(email=email).first()
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)
@app.post("/login")
async def login(request: Request,session: SessionDep, email: str = Form(), password: str= Form()):
    user = session.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")
    if not verify_password(password, user.password):
        raise HTTPException(status_code=404, detail="Incorrect password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": user.email}, expires_delta=access_token_expires
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    redirect_url = "/tasks"
    response = RedirectResponse(
        redirect_url, status_code=status.HTTP_303_SEE_OTHER, headers=headers
    )
    response.set_cookie(
        key='access_token', value=access_token, httponly=True, secure=True)
    return response


@app.get("/tasks")
async def task(request: Request, session: Session = Depends(get_session),access_token:str = Cookie()):
    payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    tasks = session.query(Task).filter(Task.email == payload.get("email")).all()
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks" : tasks})


@app.get("/create_task")
async def redirect(request: Request):
    return templates.TemplateResponse("create_task.html", {"request": request})



@app.post("/create_task")
async def create_task(request: Request ,access_token:str = Cookie(),session: Session = Depends(get_session), task_date : date = Form(),task_time: time = Form(),task_name: str = Form()):
    payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    task = Task(task_date=task_date, task_time=task_time, task_name=task_name, email = payload.get("email") )
    session.add(task)
    session.commit()
    session.refresh(task)
    print("task created successfully")
    return templates.TemplateResponse("create_task.html", {"request": request})

@app.get("/api")
async def api(request: Request):
    with open("template.json", "r") as f:
        temp =  json.load(f)
        return templates.TemplateResponse("api.html", {"request": request, "tabs": temp })

@app.post("/api/tabs/{tabs_id}")
async def tabs(request: Request, tabs_id: int):
    with open("template.json", "r") as f:
        temp = json.load(f)
        tabsec = temp["tabs"][tabs_id]["tab_sections"]
        return templates.TemplateResponse("tabsection.html", {"request": request, "tabsec": tabsec})


@app.post("/api/tabs/{tabs_id}/tabsec/{tabsec_id}")
async def tabs(request: Request, tabs_id: int, tabsec_id: int):
    with open("template.json", "r") as f:
        temp = json.load(f)
        tabsec = temp["tabs"][tabs_id]["tab_sections"]
        secfeild = tabsec[tabsec_id]["section_fields"]
        return templates.TemplateResponse("fields.html", {"request": request, "secfield": secfeild})

@app.get("/register")
async def registertemplate(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})
@app.post("/register")
async def register(request: Request,session: SessionDep,name: str = Form(), email: str = Form(), password: str= Form()):
    user = User(name=name, email=email, password=get_password_hash(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return templates.TemplateResponse("index.html", {"request": request})

@app.get('/logout')
def protected_route():
    headers = {"Authorization": f"Bearer "}
    redirect_url = "/"
    response = RedirectResponse(
        redirect_url, status_code=status.HTTP_303_SEE_OTHER, headers=headers
    )
    response.set_cookie(key="access_token", value="", expires=0)
    return response
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
