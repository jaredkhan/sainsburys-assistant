import json
import os
from functools import cached_property

import click
import requests
from requests.cookies import RequestsCookieJar
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from data_model import ShoppingItem, TrolleyQuantityByItems, TrolleyQuantityByWeight, TrolleyItem, Trolley


class SainsburysAPIClient:
    """Provides a wrapper around basic Sainsbury's API calls."""
    def __init__(self, access_token: str, wc_auth_token: str, cookies: RequestsCookieJar):
        self.access_token = access_token
        self.wc_auth_token = wc_auth_token
        self.cookies = cookies

    def add_item(self, item: TrolleyItem):
        """Adds the given item to the current trolley.

        If the item already exists, the quantity will be added in addition to what's already in the trolley."""
        match item.quantity:
            case TrolleyQuantityByItems(number):
                quantity = number
                uom = "ea"
            case TrolleyQuantityByWeight(weight_kg):
                quantity = weight_kg
                uom = "kg"
            case _:
                raise ValueError(f"Unexpected item quantity type {type(item.quantity)}")

        response = requests.post(
            url="https://www.sainsburys.co.uk/groceries-api/gol-services/basket/v1/basket/item",
            json={
                "quantity": quantity,
                "uom": uom,
                "selected_catchweight": "",
                "product_uid": item.id,
            },
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "WCAuthToken": self.wc_auth_token,
            },
            cookies=self.cookies
        )
        assert response.ok, response.json()

    def capture_trolley(self) -> Trolley:
        response = requests.get(
            url="https://www.sainsburys.co.uk/groceries-api/gol-services/basket/v1/basket",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "WCAuthToken": self.wc_auth_token,
            },
            cookies=self.cookies
        )
        assert response.ok
        response_json = response.json()
        assert "items" in response_json
        return Trolley(items=[
            TrolleyItem(
                id=json_item["product"]["product_uid"],
                name=json_item["product"]["name"],
                quantity=(
                    TrolleyQuantityByWeight(json_item["quantity"])
                    if json_item["uom"] == "kg"
                    else TrolleyQuantityByItems(json_item["quantity"])
                )
            )
            for json_item in response_json["items"]
        ])

    def empty_trolley(self):
        response = requests.delete(
            url="https://www.sainsburys.co.uk/groceries-api/gol-services/basket/v1/basket",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "WCAuthToken": self.wc_auth_token,
            },
            cookies=self.cookies
        )
        assert response.ok, response.text


class SainsburysShoppingDriver:
    """
    Provides basic programmatic control of an interactive Sainsbury's browser session.
    """
    def __init__(self):
        self._driver = webdriver.Firefox()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._driver.quit()

    def refresh(self):
        self._driver.refresh()

    @cached_property
    def api(self) -> SainsburysAPIClient:
        """A Sainsbury's API Client constructed using credentials from the browser instance."""
        access_token = json.loads(
            self._driver.execute_script(
                "return window.localStorage.getItem('oidc.user:https://account.sainsburys.co.uk:gol');"
            )
        )["access_token"]
        wc_auth_token = next(
            cookie["value"]
            for cookie in self._driver.get_cookies()
            if cookie["name"].startswith("WC_AUTHENTICATION_")
        )
        cookie_jar = requests.cookies.RequestsCookieJar()
        for cookie in self._driver.get_cookies():
            cookie_jar.set(name=cookie["name"], value=cookie["value"], domain=cookie["domain"], path=cookie["path"])

        return SainsburysAPIClient(
            access_token=access_token,
            wc_auth_token=wc_auth_token,
            cookies=cookie_jar,
        )

    def _accept_cookies(self):
        cookie_button = WebDriverWait(self._driver, 5).until(
            EC.presence_of_element_located((By.ID, "onetrust-accept-btn-handler"))
        )
        self._driver.execute_script("""document.getElementById("onetrust-accept-btn-handler").click()""")
        cookie_button.click()
        WebDriverWait(self._driver, 10).until(EC.invisibility_of_element(cookie_button))

    def login(self):
        if 'SAINSBURYS_EMAIL' not in os.environ or 'SAINSBURYS_PASSWORD' not in os.environ:
            print("In order to login automatically, please set the SAINSBURYS_EMAIL and SAINSBURYS_PASSWORD environment variables.")
        self._driver.get(
            "https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/LogonView?catalogId=10122&langId=44&storeId=10151&logonCallerId=LogonButton&URL=TopCategoriesDisplayView")
        assert "Sainsbury's" in self._driver.title
        self._accept_cookies()
        WebDriverWait(self._driver, 3).until(
            EC.presence_of_element_located((By.ID, "username"))
        ).send_keys(os.environ['SAINSBURYS_EMAIL'])
        self._driver.find_element(By.ID, "password").send_keys(os.environ['SAINSBURYS_PASSWORD'])
        self._driver.find_element(By.ID, "password").send_keys(Keys.RETURN)
        try:
            # High timeout as might need to wait for user to enter verification code
            WebDriverWait(self._driver, 300).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CLASS_NAME, "loggedOutLink")),
                    EC.presence_of_element_located((By.CLASS_NAME, "top-right-links--logout"))
                )
            )
        except TimeoutException:
            print("Did not detect login")
            self._driver.quit()
            exit(1)

    def _find_search_bar_element(self) -> WebElement:
        try:
            return self._driver.find_element(By.ID, "search")
        except NoSuchElementException:
            return self._driver.find_element(By.ID, "search-bar-input")

    def search_for_item(self, item: ShoppingItem):
        """Enters the name of the given shopping item into the search bar and starts the search.

        Does *not* wait for results to be shown."""
        search_bar_element = self._find_search_bar_element()
        search_term = item.trolley_item.name if item.trolley_item else item.display_name
        search_bar_element.clear()
        search_bar_element.send_keys(search_term)
        search_bar_element.send_keys(Keys.RETURN)
