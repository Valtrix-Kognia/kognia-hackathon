from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "voice_configured": request.app.state.session_service.is_configured(),
        "dataset": request.app.state.settings.socrata_dataset_id,
    }
