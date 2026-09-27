from fastapi import HTTPException, status

class TokenBudgetExceeded(HTTPException):
    def __init__(self, budget: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Request exceeds configured token budget ({budget} tokens).",
        )

class TokenBudget:
    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    def check(self, estimated_prompt_tokens: int, max_completion: int) -> None:
        if estimated_prompt_tokens + max_completion > self.max_tokens:
            raise TokenBudgetExceeded(self.max_tokens)
