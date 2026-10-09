from pydantic import Field

from app.domain.models.dataset_columns import Dimension, Metric
from app.domain.models.filter_request import FilterRequest


class GroupQuery(FilterRequest):
    dimension: Dimension
    metric: Metric = Metric.PRESTADORES
    top_n: int = Field(default=10, ge=1, le=40)
    ascending: bool = False

    def filters(self) -> FilterRequest:
        return FilterRequest.model_validate(
            self.model_dump(include=set(FilterRequest.model_fields))
        )


class SearchQuery(FilterRequest):
    page: int = Field(default=1, ge=1, le=200)
    page_size: int = Field(default=10, ge=1, le=25)

    def filters(self) -> FilterRequest:
        return FilterRequest.model_validate(
            self.model_dump(include=set(FilterRequest.model_fields))
        )
