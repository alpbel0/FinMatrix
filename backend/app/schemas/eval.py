from pydantic import BaseModel


class EvalStats(BaseModel):
    total_runs: int = 0
    hallucination_count: int = 0
