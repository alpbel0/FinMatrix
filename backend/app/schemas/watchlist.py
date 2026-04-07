from pydantic import BaseModel


class WatchlistItem(BaseModel):
    stock_id: int
    notifications_enabled: bool = True
