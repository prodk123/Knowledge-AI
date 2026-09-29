"""Safe Calculator Tool."""

import ast
import operator
from pydantic import BaseModel, Field

from app.agent.tools.base import BaseTool, RequestContext, ToolRiskLevel, ToolCapability


class CalculatorInput(BaseModel):
    expression: str = Field(..., description="The mathematical expression to evaluate (e.g., '(125 * 24) / 2').")


class CalculatorOutput(BaseModel):
    result: float = Field(..., description="The evaluated result.")


class SafeMathVisitor(ast.NodeVisitor):
    """Safely evaluates basic math AST nodes."""
    
    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    def visit_BinOp(self, node: ast.BinOp) -> float:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type not in self.ALLOWED_OPS:
            raise ValueError(f"Unsupported operation: {op_type.__name__}")
        return self.ALLOWED_OPS[op_type](left, right)
        
    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type not in self.ALLOWED_OPS:
            raise ValueError(f"Unsupported operation: {op_type.__name__}")
        return self.ALLOWED_OPS[op_type](operand)
        
    def visit_Constant(self, node: ast.Constant) -> float:
        if not isinstance(node.value, (int, float)):
            raise ValueError("Only numbers are allowed.")
        return float(node.value)
        
    def visit_Expr(self, node: ast.Expr) -> float:
        return self.visit(node.value)
        
    def generic_visit(self, node: ast.AST):
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Perform precise deterministic arithmetic calculations. Supports +, -, *, / and parentheses. Do NOT use for general code execution."
    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW
    capabilities = [ToolCapability.READ]
    
    input_schema = CalculatorInput
    output_schema = CalculatorOutput
    
    async def execute(self, context: RequestContext, arguments: CalculatorInput) -> CalculatorOutput:
        try:
            # Parse the expression into an AST
            tree = ast.parse(arguments.expression, mode='eval')
            # Evaluate safely
            visitor = SafeMathVisitor()
            result = visitor.visit(tree.body)
            return CalculatorOutput(result=result)
        except ZeroDivisionError:
            raise ValueError("Division by zero is not allowed.")
        except Exception as e:
            raise ValueError(f"Invalid math expression: {str(e)}")
