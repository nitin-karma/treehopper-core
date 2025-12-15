from treehopper.th_config import ALLOWED_EVENT_TYPES


def validate_event(event: dict):
    if "type" not in event:
        raise RuntimeError("WS event missing 'type'")

    if event["type"] not in ALLOWED_EVENT_TYPES:
        raise RuntimeError(f"Unknown WS event type: {event['type']}")
