import click
from tqdm import tqdm

from data_model import TrolleyQuantityByItems, TrolleyQuantityUnit, TrolleyQuantityByWeight, ShoppingItem, TrolleyItem
from evaluate_math import evaluate_math_expression
from notion_data_provider import get_items, store_sainsburys_info_for_item
from shopping_driver import SainsburysShoppingDriver


def main():
    click.secho("        Sainsbury's Assistant        ", fg="black", bg=208, bold=False)
    items = get_items()

    with SainsburysShoppingDriver() as driver:
        click.echo("Logging in...", nl=False)
        driver.login()

        click.echo("\rPress any key when ready to empty trolley and add items", nl=False)
        click.getchar()

        driver.api.empty_trolley()
        items_to_order_manually = automatically_order(driver, items)

        if items_to_order_manually:
            print(f"\nPlease manually add the remaining {len(items_to_order_manually)} items:")

        for item_index, item in enumerate(items_to_order_manually):
            driver.search_for_item(item)
            old_trolley = driver.api.capture_trolley()
            click.echo(
                f"({item_index + 1}/{len(items_to_order_manually)}) "
                f"Add {item.display_name} ({item.display_quantity}) "
                f"then press any key to save and continue, [m] to set manual ratio, or [x] to skip saving")

            char = click.getchar()
            click.echo()

            if char != "x":
                new_items_in_trolley = driver.api.capture_trolley().items_added(since=old_trolley)
                if len(new_items_in_trolley) != 1 or item.display_quantity.value <= 0:
                    click.echo("Found no or multiple new items in trolley so did not record choice")
                    continue

                new_item_in_trolley = new_items_in_trolley[0]
                try:
                    record_item_association(
                        get_manual_multiplier=char == "m",
                        shopping_item=item,
                        trolley_item=new_item_in_trolley,
                    )
                except ValueError as e:
                    print(f"Encountered error when recording item association for: {item.display_name}")
                    print(e)
        input("Finished list. Press [Enter] to quit")


def record_item_association(get_manual_multiplier: bool, shopping_item: ShoppingItem, trolley_item: TrolleyItem):
    if isinstance(trolley_item.quantity, TrolleyQuantityByItems):
        unit = TrolleyQuantityUnit.ITEMS
    elif isinstance(trolley_item.quantity, TrolleyQuantityByWeight):
        unit = TrolleyQuantityUnit.KILOGRAMS
    else:
        click.echo(f"Found unexpected quantity type in item: {type(trolley_item.quantity)}")
        return

    multiplier = (trolley_item.quantity.number_of_items if unit == TrolleyQuantityUnit.ITEMS else trolley_item.quantity.weight_kg) / shopping_item.display_quantity.value
    unit_display_name = 'items' if unit == TrolleyQuantityUnit.ITEMS else 'kg'
    if get_manual_multiplier:
        multiplier = None
        while multiplier is None:
            try:
                multiplier = evaluate_math_expression(click.prompt(
                    f"Detected '{trolley_item.name}' for Notion item '{shopping_item.display_name}'. "
                    f"Set ratio [{unit_display_name}/{shopping_item.display_quantity.unit or 'item'}]: "))
            except ValueError as e:
                click.secho(str(e), fg="red")
    click.echo(
        f"Recorded '{trolley_item.name}' ({multiplier} {unit_display_name}/{shopping_item.display_quantity.unit or 'item'})")
    store_sainsburys_info_for_item(
        shopping_item.display_name,
        multiplier=multiplier,
        sainsburys_item_name=trolley_item.name,
        sainsburys_product_uid=trolley_item.id,
        unit=unit
    )


def automatically_order(driver, items):
    items_to_order_manually = []

    print("\rAdding items to trolley...                                    ")
    for item in tqdm(items):
        if item.trolley_item:
            try:
                driver.api.add_item(item.trolley_item)
                continue
            except Exception as e:
                click.secho(f"Failed to automatically order {item.display_name}: {e}")
        items_to_order_manually.append(item)
    driver.refresh()
    return items_to_order_manually


if __name__ == '__main__':
    main()
