import ast
import math
import operator
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


STATIC_DIR = Path(__file__).parent / "static"
MAX_EXPRESSION_LENGTH = 256
MAX_EXPONENT = 1000

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

app = FastAPI(title="Calculator API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CalculationRequest(BaseModel):
    expression: Annotated[str, Field(min_length=1, max_length=MAX_EXPRESSION_LENGTH)]


def evaluate_expression(expression: str) -> int | float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Enter a valid arithmetic expression.") from exc

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
                raise ValueError(f"Exponents must be between -{MAX_EXPONENT} and {MAX_EXPONENT}.")
            value = OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            value = OPERATORS[type(node.op)](evaluate(node.operand))
        else:
            raise ValueError("Only numbers and +, -, *, /, %, **, and parentheses are supported.")

        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("The result is too large to represent.")
        if isinstance(value, int) and value.bit_length() > 1024:
            raise ValueError("The result is too large to represent.")
        return value

    return evaluate(tree.body)


@app.get("/", include_in_schema=False)
async def calculator_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/calc")
async def calculate(request: CalculationRequest) -> dict[str, int | float | str]:
    try:
        result = evaluate_expression(request.expression)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"expression": request.expression, "result": result}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)