from treehopper.th_config import ALLOWED_EVENT_TYPES, REQUIRED_FIELDS


def validate_event(event: dict) -> None:
    if not isinstance(event, dict):
        raise ValueError("WS event must be a dict")

    event_type = event.get("type")
    if not event_type:
        raise ValueError("WS event missing 'type'")

    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Invalid WS event type: {event_type}")

    required = REQUIRED_FIELDS.get(event_type, [])
    for field in required:
        if field not in event:
            raise ValueError(
                f"WS event '{event_type}' missing required field '{field}'"
            )
