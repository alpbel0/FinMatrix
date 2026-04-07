from pydantic import BaseModel


class StockResponse(BaseModel):
    symbol: str
    company_name: str | None = None
    sector: str | None = None
