from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.request_log import RequestLog
from src.infrastructure.orm.models import RequestLogORM


def _orm_to_domain(row: RequestLogORM) -> RequestLog:
    return RequestLog(
        id=row.id,
        user_id=row.user_id,
        account_id=row.account_id,
        request_id=row.request_id,
        model=row.model,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cache_read_tokens=row.cache_read_tokens,
        cache_write_tokens=row.cache_write_tokens,
        prompt_content=row.prompt_content,
        response_content=row.response_content,
        status_code=row.status_code,
        error_type=row.error_type,
        duration_ms=row.duration_ms,
        is_streaming=row.is_streaming,
        created_at=row.created_at,
    )


class SqlLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: RequestLog) -> None:
        row = RequestLogORM(
            user_id=log.user_id,
            account_id=log.account_id,
            request_id=log.request_id,
            model=log.model,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            cache_read_tokens=log.cache_read_tokens,
            cache_write_tokens=log.cache_write_tokens,
            prompt_content=log.prompt_content,
            response_content=log.response_content,
            status_code=log.status_code,
            error_type=log.error_type,
            duration_ms=log.duration_ms,
            is_streaming=log.is_streaming,
        )
        self._session.add(row)
        await self._session.commit()

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RequestLog]:
        result = await self._session.execute(
            select(RequestLogORM)
            .where(RequestLogORM.user_id == user_id)
            .order_by(RequestLogORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_orm_to_domain(r) for r in result.scalars().all()]

    async def get_user_stats(self, user_id: UUID, days: int = 30) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(
                func.count(RequestLogORM.id).label("total_requests"),
                func.coalesce(func.sum(RequestLogORM.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RequestLogORM.output_tokens), 0).label(
                    "total_output_tokens"
                ),
            ).where(
                RequestLogORM.user_id == user_id,
                RequestLogORM.created_at >= since,
            )
        )
        row = result.one()

        # Model breakdown
        model_result = await self._session.execute(
            select(
                RequestLogORM.model,
                func.count(RequestLogORM.id).label("count"),
                func.coalesce(
                    func.sum(RequestLogORM.input_tokens + RequestLogORM.output_tokens), 0
                ).label("tokens"),
            )
            .where(RequestLogORM.user_id == user_id, RequestLogORM.created_at >= since)
            .group_by(RequestLogORM.model)
            .order_by(text("count DESC"))
        )

        return {
            "total_requests": row.total_requests,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "models": [
                {"model": r.model, "count": r.count, "tokens": r.tokens} for r in model_result.all()
            ],
        }

    async def get_overview_stats(self, days: int = 1) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(
                func.count(RequestLogORM.id).label("total_requests"),
                func.count(RequestLogORM.user_id.distinct()).label("active_users"),
                func.coalesce(func.sum(RequestLogORM.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RequestLogORM.output_tokens), 0).label(
                    "total_output_tokens"
                ),
            ).where(RequestLogORM.created_at >= since)
        )
        row = result.one()
        return {
            "total_requests": row.total_requests,
            "active_users": row.active_users,
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
        }

    async def get_account_stats(self, days: int = 30) -> list[dict]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(
                RequestLogORM.account_id,
                func.count(RequestLogORM.id).label("count"),
                func.coalesce(func.sum(RequestLogORM.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLogORM.output_tokens), 0).label("output_tokens"),
            )
            .where(RequestLogORM.created_at >= since, RequestLogORM.account_id.isnot(None))
            .group_by(RequestLogORM.account_id)
            .order_by(text("count DESC"))
        )
        return [
            {
                "account_id": str(r.account_id),
                "count": r.count,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
            }
            for r in result.all()
        ]

    async def get_model_stats(self, days: int = 30) -> list[dict]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(
                RequestLogORM.model,
                func.count(RequestLogORM.id).label("count"),
                func.coalesce(func.sum(RequestLogORM.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLogORM.output_tokens), 0).label("output_tokens"),
            )
            .where(RequestLogORM.created_at >= since)
            .group_by(RequestLogORM.model)
            .order_by(text("count DESC"))
        )
        return [
            {
                "model": r.model,
                "count": r.count,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
            }
            for r in result.all()
        ]
