from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.event_sourcing import rebuild_state
from core.goal_service import GoalService
from core.models import UserProfile

router = APIRouter()


def get_goal_service() -> GoalService:
    return GoalService()


class GenerateFilter(BaseModel):
    n: int = 3


class GenerateResponse(BaseModel):
    candidates: List[dict]
    message: str


class ConfirmRequest(BaseModel):
    goal: Dict[str, Any]


@router.post("/generate", response_model=GenerateResponse)
def generate_goals(filter: GenerateFilter):
    state = rebuild_state()
    profile = state.get("profile")
    if not isinstance(profile, UserProfile):
        profile = UserProfile()

    if not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Onboarding not completed")

    service = get_goal_service()
    candidates = service.generate_candidates(n=filter.n)
    return GenerateResponse(
        candidates=candidates,
        message=f"Based on your focus on {profile.focus_area}, here are some suggestions.",
    )


@router.post("/confirm")
def confirm_goal(req: ConfirmRequest):
    service = get_goal_service()
    goal_data = dict(req.goal)
    goal_data.pop("_score", None)

    try:
        node, tasks_created = service.confirm_candidate_goal(goal_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "goal_id": node.id,
        "tasks_created": tasks_created,
    }


@router.get("/list")
def list_goals():
    service = get_goal_service()
    all_nodes = service.list_nodes()
    active = [
        service.node_to_dict(n, include_legacy=True)
        for n in all_nodes
        if n.state.value == "active"
    ]
    completed = [
        service.node_to_dict(n, include_legacy=True)
        for n in all_nodes
        if n.state.value == "completed"
    ]
    return {"active": active, "completed": completed}


class VisionRequest(BaseModel):
    title: str
    description: str = ""
    source: str = "user_input"


@router.post("/vision")
def create_vision(req: VisionRequest):
    service = get_goal_service()
    node = service.create_vision(req.title, req.description, req.source)
    return {"success": True, "vision_id": node.id}


class DecomposeRequest(BaseModel):
    selected_option: Optional[Dict[str, Any]] = None
    custom_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.get("/{goal_id}/questions")
def get_decomposition_questions(goal_id: str):
    service = get_goal_service()
    try:
        questions = service.get_decomposition_questions(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"questions": questions}


@router.post("/{goal_id}/decompose")
def decompose_goal(goal_id: str, req: Optional[DecomposeRequest] = None):
    service = get_goal_service()

    try:
        if req is None or (not req.selected_option and not req.custom_input):
            return service.get_decomposition_options(
                goal_id,
                context=req.context if req else None,
                n=3,
            )

        child, tasks_created, existed = service.create_decomposed_child(
            goal_id=goal_id,
            selected_option=req.selected_option,
            custom_input=req.custom_input,
        )

        payload = service.node_to_dict(child, include_legacy=True)
        response = {
            "success": True,
            "goal": payload,
            "tasks_created": tasks_created,
        }
        if existed:
            response["message"] = "Goal already exists"
        return response
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Goal not found")
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{goal_id}")
def delete_goal(goal_id: str):
    service = get_goal_service()
    try:
        service.archive_goal(goal_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"success": True}


@router.get("/tree")
def get_goal_tree():
    service = get_goal_service()
    return {"tree": service.get_goal_tree(only_active=True)}
