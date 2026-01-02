from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AgentState(BaseModel):
    project_root: str
    context: Dict[str, Any] = Field(default_factory=dict)

    hypothesis: Optional[str] = None
    confidence: Optional[float] = None

    checks_remaining: List[str] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)

    verified: bool = False
    final_output: Optional[str] = None
