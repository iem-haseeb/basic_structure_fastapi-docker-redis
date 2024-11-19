from typing import Annotated, Type

from fastapi import Form, Depends,  FastAPI, Request
import redis
from fastapi.templating import Jinja2Templates
from sqlmodel import Field, Session, SQLModel, create_engine, select


class User(SQLModel, table=True):
    name: str = Field(index=False)
    email: str | None = Field(default=None,primary_key=True)
    password: str = Field(index=True)

app = FastAPI()

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]


templates = Jinja2Templates(directory="templates")

# Initialize Redis connection
r = redis.Redis(host="redis", port=6379, db=0)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/user")
async def login(session: SessionDep, name: str = Form(), email: str = Form(), password: str= Form()):
    u = User()
    u.email = email
    u.name = name
    u.password = password
    session.add(u)
    print("///////////////////////////////////////////////")
    session.commit()
    session.refresh(u)
    return {"name": name,"email": email, "password": password}
