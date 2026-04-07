from pydantic import BaseModel


class FinancialSummary(BaseModel):
    revenue: float | None = None
    net_income: float | None = None
