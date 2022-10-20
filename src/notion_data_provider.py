"""
A data provider that assumes a certain layout of Notion database
and uses that as a persistent data store and source of the shopping list.
"""
import math
import os

import click
import requests

from data_model import ShoppingItem, TrolleyQuantityUnit, TrolleyItem, TrolleyQuantity, TrolleyQuantityByItems, \
    TrolleyQuantityByWeight, DisplayQuantity

if 'NOTION_SECRET' not in os.environ or 'NOTION_SHOPPING_ITEM_DB' not in os.environ or 'NOTION_RECIPE_DB' not in os.environ:
    print(
        "In order to use the Notion data provider for Sainsbury's, please set: \n"
        "- the NOTION_SECRET environment variable to a secret for a Connection in your Notion workspace "
        "that has access to your grocery databases, \n"
        "- the NOTION_SHOPPING_ITEM_DB environment variable to the ID of the Shopping Item database in your Notion "
        "workspace, \n"
        "- the NOTION_RECIPE_DB environment variable to the ID of the Recipe database in your Notion workspace.\n"
        "Note that your databases have to have a very specific structure which is only specified in the source code "
        "of this app.")

notion_secret = os.environ['NOTION_SECRET']
notion_shopping_items_db = os.environ['NOTION_SHOPPING_ITEM_DB']
notion_recipes_db = os.environ['NOTION_RECIPE_DB']


def get_items() -> list[ShoppingItem]:
    response = requests.post(
        url=f"https://api.notion.com/v1/databases/{notion_shopping_items_db}/query",
        headers={
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "filter": {
                "and": [
                    {
                        "or": [
                            {
                                "property": "Total Needed",
                                "formula": {
                                    "number": {
                                        "greater_than": 0
                                    }
                                }
                            },
                            {
                                "property": "Weekly Item",
                                "checkbox": {
                                    "equals": True
                                }
                            },
                            {
                                "property": "Extra Item",
                                "checkbox": {
                                    "equals": True
                                }
                            },
                            {
                                "property": "Manual quantity",
                                "number": {
                                    "is_not_empty": True
                                }
                            },
                            {
                                "property": "On-demand Item",
                                "checkbox": {
                                    "equals": True
                                }
                            }
                        ]
                    },
                    {
                        "property": "Stocked?",
                        "checkbox": {
                            "equals": False
                        }
                    }
                ]
            },
            "sorts": [
                {
                    "property": "Aisle",
                    "direction": "ascending"
                },
                {
                    "property": "Grocery",
                    "direction": "ascending"
                }
            ]
        }
    )

    assert response.json()["has_more"] is False
    results = response.json()["results"]
    quantity_in_meals_for_item_id = get_quantity_in_meals_for_item_id_dict()
    shopping_items = [
        shopping_item_for_result(result, quantity_in_meals_for_item_id)
        for result
        in results
    ]
    zero_quantity_shopping_items = [
        shopping_item.display_name
        for shopping_item in shopping_items
        if shopping_item.display_quantity.value == 0
    ]
    if zero_quantity_shopping_items:
        click.secho(f"⚠️ The following items have a quantity of 0 and will be skipped: {zero_quantity_shopping_items}", fg="yellow")
    non_zero_quantity_shopping_items = [
        shopping_item
        for shopping_item in shopping_items
        if not (shopping_item.display_quantity.value == 0)
    ]

    return non_zero_quantity_shopping_items


def shopping_item_for_result(result: dict, quantity_in_meals_for_item_id: dict[str, float]) -> ShoppingItem:
    total_needed = quantity_in_meals_for_item_id.get(result["id"], 0) + (
                result["properties"]["Manual quantity"]["number"] or 0)
    if total_needed == 0 and (result["properties"]["Extra Item"]["checkbox"] or result["properties"]["Weekly Item"]["checkbox"] or result["properties"]["On-demand Item"]["checkbox"]):
        # Some items will be marked as required without an explicit quantity, use default of 1 unit
        total_needed = 1
    unit_string = result["properties"]["Unit"]["rich_text"][0]["plain_text"] if result["properties"]["Unit"][
        "rich_text"] else None
    return ShoppingItem(
        display_name=result["properties"]["Grocery"]["title"][0]["plain_text"],
        display_quantity=DisplayQuantity(value=total_needed, unit=unit_string),
        trolley_item=trolley_item_for_result(result, total_needed),
    )


def trolley_item_for_result(result: dict, total_needed: float) -> TrolleyItem | None:
    if (
            result["properties"]["Sainsbury's Item Name"]["rich_text"] and
            result["properties"]["Sainsbury's Unit"]["select"] and
            result["properties"]["Sainsbury's Multiplier"]["number"] and
            result["properties"]["Sainsbury's Product UID"]["rich_text"]
    ):
        return TrolleyItem(
            id=result["properties"]["Sainsbury's Product UID"]["rich_text"][0]["plain_text"],
            name=result["properties"]["Sainsbury's Item Name"]["rich_text"][0]["plain_text"],
            quantity=trolley_quantity_for_result(result, total_needed)
        )
    return None


def trolley_quantity_for_result(result: dict, total_needed: float) -> TrolleyQuantity:
    assert "name" in result["properties"]["Sainsbury's Unit"]["select"]
    value = total_needed * result["properties"]["Sainsbury's Multiplier"]["number"]
    match result["properties"]["Sainsbury's Unit"]["select"]["name"]:
        case "Items":
            tolerance = 0.2
            if value != 0 and value <= tolerance:
                # Make sure we get things that we need even if we don't need much of them
                value = 1
            return TrolleyQuantityByItems(number_of_items=math.ceil(value - tolerance))
        case "Kilograms":
            return TrolleyQuantityByWeight(weight_kg=value)
        case unrecognised_unit:
            raise ValueError(f"Encountered unrecognised Sainsbury's Unit value '{unrecognised_unit}'")


def get_quantity_in_meals_for_item_id_dict() -> dict[str, float]:
    # Due to notion API limitation
    # Get ingredients with this item
    filter = {
        "property": "Total Needed",
        "formula": {
            "number": {
                "greater_than": 0
            }
        }
    }
    response = requests.post(
        url=f"https://api.notion.com/v1/databases/{notion_recipes_db}/query",
        headers={
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "filter": filter
        }
    )
    results = response.json()["results"]
    while response.json()["has_more"]:
        response = requests.post(
            url=f"https://api.notion.com/v1/databases/{notion_recipes_db}/query",
            headers={
                "Authorization": f"Bearer {notion_secret}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "filter": filter,
                "start_cursor": response.json()["next_cursor"]
            }
        )
        results += response.json()["results"]

    result_ids = [result["id"] for result in results]
    # Check didn't double count any
    assert len(result_ids) == len(set(result_ids))

    quantity_dict = {}

    for result in results:
        assert len(result["properties"]["Item"]["relation"]) == 1
        item_id = result["properties"]["Item"]["relation"][0]["id"]
        if item_id not in quantity_dict:
            quantity_dict[item_id] = 0
        quantity_dict[item_id] += result["properties"]["Total Needed"]["formula"]["number"]

    return quantity_dict


def store_sainsburys_info_for_item(item_name: str, multiplier: float, sainsburys_item_name: str, sainsburys_product_uid: str,
                                   unit: TrolleyQuantityUnit):
    response = requests.post(
        url=f"https://api.notion.com/v1/databases/{notion_shopping_items_db}/query",
        headers={
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "filter": {
                "property": "Grocery",
                "title": {
                    "equals": item_name
                }
            }
        }
    )

    assert response.json()["has_more"] is False
    results = response.json()["results"]
    if len(results) != 1:
        raise ValueError(f"Multiple shopping items in database with the name {item_name}")

    item_id = results[0]["id"]

    response = requests.patch(
        url=f"https://api.notion.com/v1/pages/{item_id}",
        headers={
            "Authorization": f"Bearer {notion_secret}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={
            "properties": {
                "Sainsbury's Multiplier": {
                    "number": multiplier
                },
                "Sainsbury's Item Name": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": sainsburys_item_name
                            }
                        }
                    ]
                },
                "Sainsbury's Product UID": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": sainsburys_product_uid
                            }
                        }
                    ]
                },
                "Sainsbury's Unit": {
                    "select": {
                        "name": unit.value
                    }
                }
            }
        }
    )
    assert response.ok, response.json()
