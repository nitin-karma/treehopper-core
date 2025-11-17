from pydantic import BaseModel
from fastapi import Body
from treehopper.treehopper import agent


class MathExpression(BaseModel):
    expression: str | None = None
    a: float | None = None
    b: float | None = None


@agent(
    "math",
    method="POST",
    goal="Perform simple math: expression='2+3' OR a,b → a+b",
    tags=["Example Agents"],
)
async def math(
    req: MathExpression = Body(None),
    expression: str | None = None,
    a: float | None = None,
    b: float | None = None,
):
    """
    Supports both:
    - { "expression": "2+3" }
    - { "a": 2, "b": 3 }
    - Chaining calls: {"params": {"a": 2, "b": 3}}
    """

    # Operand mode
    if a is not None and b is not None:
        return {"result": a + b}

    # Expression mode (HTTP body / direct)
    if expression:
        return {"result": eval(expression)}

    if req:
        # From HTTP body "expression"
        if req.expression:
            return {"result": eval(req.expression)}
        # From HTTP body operands "a", "b"
        if req.a is not None and req.b is not None:
            return {"result": req.a + req.b}

    return {"error": "Missing input. Provide expression OR a & b"}
