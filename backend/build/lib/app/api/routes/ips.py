from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_ips_service
from app.api.schemas.ips_queries import GroupQuery, SearchQuery
from app.application.services.ips_query_service import IpsQueryService
from app.domain.models.filter_request import FilterRequest
from app.domain.models.query_results import (
    CountResult,
    DatasetOverview,
    GroupResult,
    IpsDetail,
    SearchResult,
)

router = APIRouter(prefix="/api/v1/ips", tags=["ips"])
Service = Annotated[IpsQueryService, Depends(get_ips_service)]
Filters = Annotated[FilterRequest, Query()]


@router.get("/overview", response_model=DatasetOverview)
async def overview(service: Service) -> DatasetOverview:
    return await service.overview()


@router.get("/count", response_model=CountResult)
async def count(service: Service, filters: Filters) -> CountResult:
    return await service.count(filters)


@router.get("/group", response_model=GroupResult)
async def group(service: Service, query: Annotated[GroupQuery, Query()]) -> GroupResult:
    return await service.group(
        query.dimension,
        query.metric,
        query.filters(),
        top_n=query.top_n,
        ascending=query.ascending,
    )


@router.get("/search", response_model=SearchResult)
async def search(
    service: Service, query: Annotated[SearchQuery, Query()]
) -> SearchResult:
    return await service.search(
        query.filters(), page=query.page, page_size=query.page_size
    )


@router.get("/sites/{codigo_sede}", response_model=IpsDetail)
async def details(service: Service, codigo_sede: str) -> IpsDetail:
    detail = await service.details(codigo_sede)
    if detail is None:
        raise HTTPException(
            status_code=404, detail="Sede no encontrada en la fuente oficial."
        )
    return detail
