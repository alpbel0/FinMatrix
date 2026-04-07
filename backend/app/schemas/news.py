from pydantic import BaseModel


class NewsItem(BaseModel):
    id: int
    title: str
    category: str | None = None
