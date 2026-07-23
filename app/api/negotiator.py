from fastapi import APIRouter
from pydantic import BaseModel
from app.models.llm_agents import AINegotiator

router = APIRouter()

class NegotiateRequest(BaseModel):
    product_name: str
    original_price: float
    min_price: float
    user_offer: float
    history: list = []

@router.post("/negotiate")
def start_negotiation(data: NegotiateRequest):
    negotiator = AINegotiator(data.product_name, data.original_price, data.min_price)
    ai_response = negotiator.negotiate(data.user_offer, data.history)
    
    return {
        "status": "success",
        "ai_response": ai_response
    }