from typing import TypedDict, NotRequired


class PSMetadata(TypedDict, total=False):
    data_sources: list[str]
    output_destination: str
    risk_tags: list[str]


class PSConfig(TypedDict):
    ps_api_key: str
    ps_collector_url: str
    business_unit: NotRequired[str]
    use_case: NotRequired[str]
    owner: NotRequired[str]
    data_classification: NotRequired[str]
    environment: NotRequired[str]
