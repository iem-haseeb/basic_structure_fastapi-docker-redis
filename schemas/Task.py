from fastapi import Form
from pydantic import BaseModel
from datetime import date, time


class Task(BaseModel):
    task_date: date
    task_time: time
    task_name: str


    @classmethod
    def as_form(
        cls,
        task_date: date = Form(...),
        task_time: time = Form(...),
        task_name: str = Form(...),


    ):
        return cls(
            task_date = task_date,
            task_time = task_time,
            task_name=task_name,
        )
