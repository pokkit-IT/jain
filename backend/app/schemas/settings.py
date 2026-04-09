from pydantic import BaseModel


class AgentSettings(BaseModel):
    mode: str = "copilot"  # "copilot" | "autonomous"
    radius_miles: int = 10
    llm_provider: str
    llm_model: str
