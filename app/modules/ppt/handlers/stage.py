"""Stage state machine for PPT conversation flow."""

VALID_TRANSITIONS: dict[str, list[str]] = {
    "requirement": ["requirement", "case_selection"],
    "case_selection": ["case_selection", "outline"],
    "outline": ["outline", "ppt"],
    "ppt": ["ppt", "completed"],
    "completed": ["completed"],
}


def can_transition_to(current_stage: str, target_stage: str) -> bool:
    return target_stage in VALID_TRANSITIONS.get(current_stage, [])


def infer_next_stage(conversation) -> str:
    """Infer next stage from current conversation state."""
    stage = conversation.stage
    if stage == "requirement":
        locks = conversation.metadata.get("stage_locks", {})
        if locks.get("requirement", {}).get("locked"):
            return "case_selection"
    return stage


def get_message_type(stage: str) -> str:
    return {"requirement": "text", "case_selection": "text", "outline": "outline", "ppt": "ppt"}.get(stage, "text")
