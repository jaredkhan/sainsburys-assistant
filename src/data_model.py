from enum import Enum
from typing import NamedTuple, TypeAlias


class TrolleyQuantityUnit(Enum):
    KILOGRAMS = "Kilograms"
    ITEMS = "Items"


class TrolleyQuantityByItems(NamedTuple):
    number_of_items: int

    def __bool__(self):
        return bool(self.number_of_items)

    def __sub__(self, other):
        if type(other) == TrolleyQuantityByItems:
            difference = self.number_of_items - other.number_of_items
            if difference < 0:
                raise ValueError("Unexpectedly found a difference less than zero")
            return TrolleyQuantityByItems(
                number_of_items=difference
            )
        raise TypeError(f"Cannot subtract a {type(other)} from a TrolleyQuantityByItems")


class TrolleyQuantityByWeight(NamedTuple):
    weight_kg: float

    def __bool__(self):
        return bool(self.weight_kg)

    def __sub__(self, other):
        if type(other) == TrolleyQuantityByWeight:
            difference = self.weight_kg - other.weight_kg
            if difference < 0:
                raise ValueError("Unexpectedly found a difference less than zero")
            return TrolleyQuantityByWeight(
                weight_kg=difference
            )
        raise TypeError(f"Cannot subtract a {type(other)} from a TrolleyQuantityByWeight")


TrolleyQuantity: TypeAlias = TrolleyQuantityByItems | TrolleyQuantityByWeight


class TrolleyItem(NamedTuple):
    id: str
    name: str
    quantity: TrolleyQuantity


class Trolley:
    def __init__(self, items: list[TrolleyItem]):
        self.items = items

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def items_added(self, since: "Trolley"):
        old_quantity_for_item_id = {item.id: item.quantity for item in since}
        diff_trolley = []
        for item in self.items:
            if item.id in old_quantity_for_item_id:
                diff_item = TrolleyItem(name=item.name, quantity=item.quantity - old_quantity_for_item_id[item.id],
                                       id=item.id)
                if diff_item.quantity:
                    diff_trolley.append(diff_item)
            else:
                diff_trolley.append(item)
        return diff_trolley


class DisplayQuantity(NamedTuple):
    value: int | float
    unit: str | None

    def __str__(self):
        return str(self.value) + (f" {self.unit}" if self.unit else "")


class ShoppingItem(NamedTuple):
    display_name: str
    display_quantity: DisplayQuantity
    trolley_item: TrolleyItem | None
