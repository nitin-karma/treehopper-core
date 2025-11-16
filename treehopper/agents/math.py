from treehopper.treehopper import agent

@agent("/math", method="GET", goal="Evaluate a math expression", tags=["utility", "math"])
async def math(expression: str):
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}
