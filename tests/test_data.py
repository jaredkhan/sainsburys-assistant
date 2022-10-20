from data_model import TrolleyQuantityByItems, TrolleyQuantityByWeight, TrolleyItem, Trolley


def test_can_diff_trolleys():
    old_trolley = Trolley(items=[
        TrolleyItem(id="soup", name="Sainsbury's Tomato & Basil Soup 600g (Serves 2)",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="carrot", name="Sainsbury's British Carrots Loose",
                   quantity=TrolleyQuantityByWeight(weight_kg=2.0)),
        TrolleyItem(id="potato", name="Sainsbury's British King Edward Potatoes 2kg",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="avo", name='By Sainsbury’s Medium Ripe & Ready Avocado',
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="avolarge", name='By Sainsbury’s Large Ripe & Ready Avocado',
                   quantity=TrolleyQuantityByItems(number_of_items=3)),
        TrolleyItem(id="broc", name="Sainsbury's Purple Sprouting Broccoli Spears 200g",
                   quantity=TrolleyQuantityByItems(number_of_items=2))])
    new_trolley = Trolley(items=[
        TrolleyItem(id="banana", name="Sainsbury's Fairtrade Bananas Loose",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="soup", name="Sainsbury's Tomato & Basil Soup 600g (Serves 2)",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="carrot", name="Sainsbury's British Carrots Loose",
                   quantity=TrolleyQuantityByWeight(weight_kg=2.0)),
        TrolleyItem(id="potato", name="Sainsbury's British King Edward Potatoes 2kg",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="avo", name='By Sainsbury’s Medium Ripe & Ready Avocado',
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="avolarge", name='By Sainsbury’s Large Ripe & Ready Avocado',
                   quantity=TrolleyQuantityByItems(number_of_items=4)),
        TrolleyItem(id="broc", name="Sainsbury's Purple Sprouting Broccoli Spears 200g",
                   quantity=TrolleyQuantityByItems(number_of_items=2))])

    assert list(new_trolley.items_added(since=old_trolley)) == [
        TrolleyItem(id="banana", name="Sainsbury's Fairtrade Bananas Loose",
                   quantity=TrolleyQuantityByItems(number_of_items=1)),
        TrolleyItem(id="avolarge", name='By Sainsbury’s Large Ripe & Ready Avocado',
                   quantity=TrolleyQuantityByItems(number_of_items=1))
    ]
