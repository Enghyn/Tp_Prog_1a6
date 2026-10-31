from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import asyncio
from pydantic import BaseModel
from app.core.paginacion import Page, PageParams

class Item(BaseModel):
    id: int

app = FastAPI()

@app.get("/x", response_model=Page[Item])
async def x():
    return Page(items=[Item(id=1)], total=1, page=2, size=10)

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/x")
        print(r.status_code, r.text)
    print(Page(items=[Item(id=1)], total=1, page=2, size=10).model_dump())
    print(Page(items=[Item(id=1)], total=1, page=2, size=10).model_dump_json())

asyncio.run(main())
