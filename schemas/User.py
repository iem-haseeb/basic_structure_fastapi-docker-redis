from fastapi import Form
from pydantic import BaseModel

class User(BaseModel):
    email: str
    password: str
    name: str

    @classmethod
    def as_form(
        cls,
        email: str = Form(...),
        password: str = Form(...),
        name: str = Form(...),

    ):
        return cls(
            email=email,
            password=password,
            name= name
        )



