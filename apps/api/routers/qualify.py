from fastapi import APIRouter, HTTPException

from core.llm import LLMClient
from core.prompts.qualifier import QUALIFIER_SYSTEM_PROMPT

router = APIRouter(prefix="/qualify")


@router.get("/ping")
async def qualify_ping() -> dict[str, str]:
    """Make a single test call to DeepSeek to verify the integration."""
    client = LLMClient()
    try:
        response = await client.chat(
            messages=[
                {"role": "system", "content": QUALIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": "Привет, я хочу узнать про ваши услуги."},
            ]
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"response": response}
