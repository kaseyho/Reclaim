from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


Category = Literal["furniture", "creator", "bulk"]
Condition = Literal["new", "like_new", "good", "fair", "unknown"]


class AttributeFact(StrictModel):
    key: str = Field(min_length=1,max_length=60,pattern=r"^[a-z][a-z0-9_]*$")
    value: str = Field(min_length=1,max_length=200)
    evidence: str = Field(default="Seller confirmation required",max_length=400)


class AttributeRequirement(StrictModel):
    key: str = Field(min_length=1,max_length=60,pattern=r"^[a-z][a-z0-9_]*$")
    value: str = Field(min_length=1,max_length=200)
    operator: Literal["equals","at_least","at_most","includes"] = "equals"


class SupplyUnit(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    item_type: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    quantity: int = Field(ge=1, le=100)
    reference_weight: int = Field(ge=1, le=100000)
    condition: Condition = "unknown"
    width_cm: int | None = Field(default=None, ge=1, le=1000)
    brand: str | None = Field(default=None, max_length=80)
    sealed: bool | None = None
    confirmed_fields: list[str] = Field(default_factory=list, max_length=32)
    evidence: str = Field(default="Seller confirmation required", max_length=500)
    attributes: list[AttributeFact] = Field(default_factory=list,max_length=12)

    @model_validator(mode="after")
    def unique_attributes(self):
        if len({a.key for a in self.attributes})!=len(self.attributes):
            raise ValueError("Combine values into one fact for each attribute key.")
        return self


class LotInput(StrictModel):
    title: str = Field(min_length=3, max_length=120)
    category: Category
    description: str = Field(min_length=3, max_length=4000)
    goods_price_minor: int = Field(ge=1, le=10000000)
    preparation_minor: int = Field(default=0, ge=0, le=1000000)
    currency: Literal["USD"] = "USD"
    location: str = Field(min_length=2, max_length=120)
    pickup_start: datetime
    pickup_end: datetime
    units: list[SupplyUnit] = Field(min_length=1, max_length=16)
    image: str | None = Field(default=None, max_length=4000000)
    confirmed: bool = False
    divisible: bool = False

    @model_validator(mode="after")
    def check_inventory(self):
        if len({u.id for u in self.units}) != len(self.units):
            raise ValueError("Inventory identifiers must be unique.")
        if self.pickup_start.tzinfo is None or self.pickup_end.tzinfo is None:
            raise ValueError("Pickup times require a timezone.")
        if self.pickup_start >= self.pickup_end:
            raise ValueError("Pickup end must follow pickup start.")
        if self.confirmed and not self.divisible:
            raise ValueError("Confirm that you can divide and fulfill this lot.")
        if self.confirmed and any(not {"item_type","quantity","reference_weight"}.issubset(u.confirmed_fields) for u in self.units):
            raise ValueError("Confirm each item's type, quantity and reference weight before publishing.")
        return self


class Need(StrictModel):
    item_type: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    quantity: int = Field(default=1, ge=1, le=100)
    max_width_cm: int | None = Field(default=None, ge=1, le=1000)
    minimum_condition: Condition = "good"
    brand: str | None = Field(default=None, max_length=80)
    sealed: bool | None = None
    attributes: list[AttributeRequirement] = Field(default_factory=list,max_length=12)


class DemandInput(StrictModel):
    text: str = Field(min_length=3, max_length=2000)
    needs: list[Need] = Field(min_length=1, max_length=8)
    budget_minor: int = Field(ge=1, le=10000000)
    location: str = Field(min_length=2, max_length=120)
    pickup_start: datetime
    pickup_end: datetime
    deadline: datetime
    allow_substitutions: bool = False
    confirmed: bool = False

    @model_validator(mode="after")
    def check_window(self):
        if any(x.tzinfo is None for x in [self.pickup_start, self.pickup_end, self.deadline]):
            raise ValueError("Times require a timezone.")
        if self.pickup_start >= self.pickup_end:
            raise ValueError("Pickup end must follow pickup start.")
        if len({n.item_type for n in self.needs}) != len(self.needs):
            raise ValueError("Combine quantities for duplicate item types.")
        return self


class InterpretInput(StrictModel):
    text: str = Field(min_length=3, max_length=4000)
    category: Category = "furniture"
    image: str | None = Field(default=None, max_length=4000000)


class ExtractedUnit(StrictModel):
    name: str
    item_type: str
    quantity: int
    condition: Condition
    width_cm: int | None
    brand: str | None
    sealed: bool | None
    evidence: str
    attributes: list[AttributeFact]


class Extraction(StrictModel):
    units: list[ExtractedUnit]
    unresolved: list[str]


class Interpretation(StrictModel):
    needs: list[Need]
    budget_minor: int | None
    location: str | None
    pickup_description: str | None
    allow_substitutions: bool
    unresolved: list[str]


class VersionInput(StrictModel):
    version: int = Field(ge=1)
    terms_hash: str = Field(min_length=64, max_length=64)


class AuthorizeInput(StrictModel):
    order_id: str = Field(min_length=1, max_length=100)


class PickupInput(StrictModel):
    code: str = Field(min_length=6, max_length=20)


class ProblemInput(StrictModel):
    message: str = Field(min_length=5, max_length=2000)


class SessionInput(StrictModel):
    scenario: Literal["moving", "creator", "bulk", "empty"] = "moving"


class FailureInput(StrictModel):
    kind: Literal["capture", "refund", "capture_timeout"]
    actor_id: str
