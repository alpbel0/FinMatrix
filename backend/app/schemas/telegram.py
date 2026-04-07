from pydantic import BaseModel


class TelegramLink(BaseModel):
    chat_id: str
