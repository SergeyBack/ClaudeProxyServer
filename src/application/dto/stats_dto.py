from pydantic import BaseModel


class ModelStat(BaseModel):
    model: str
    count: int
    tokens: int


class UserStatsResponse(BaseModel):
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    models: list[ModelStat]
    days: int


class OverviewStatsResponse(BaseModel):
    total_requests: int
    active_users: int
    total_input_tokens: int
    total_output_tokens: int
    days: int


class AccountStatItem(BaseModel):
    account_id: str
    count: int
    input_tokens: int
    output_tokens: int


class ModelStatItem(BaseModel):
    model: str
    count: int
    input_tokens: int
    output_tokens: int
