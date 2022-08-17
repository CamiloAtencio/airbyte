#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import datetime
import json
import os
import random
from typing import Dict, Generator

from airbyte_cdk.logger import AirbyteLogger
from airbyte_cdk.models import (
    AirbyteCatalog,
    AirbyteConnectionStatus,
    AirbyteMessage,
    AirbyteRecordMessage,
    AirbyteStateMessage,
    AirbyteStream,
    ConfiguredAirbyteCatalog,
    Status,
    Type,
)
from airbyte_cdk.sources import Source
from faker import Faker


class SourceFaker(Source):
    def check(self, logger: AirbyteLogger, config: Dict[str, any]) -> AirbyteConnectionStatus:
        """
        Tests if the input configuration can be used to successfully connect to the integration
            e.g: if a provided Stripe API token can be used to connect to the Stripe API.

        :param logger: Logging object to display debug/info/error to the logs
            (logs will not be accessible via airbyte UI if they are not passed to this logger)
        :param config: Json object containing the configuration of this source, content of this json is as specified in
        the properties of the spec.json file

        :return: AirbyteConnectionStatus indicating a Success or Failure
        """

        # As this is an in-memory source, it always succeeds
        return AirbyteConnectionStatus(status=Status.SUCCEEDED)

    def discover(self, logger: AirbyteLogger, config: Dict[str, any]) -> AirbyteCatalog:
        """
        Returns an AirbyteCatalog representing the available streams and fields in this integration.
        For example, given valid credentials to a Postgres database,
        returns an Airbyte catalog where each postgres table is a stream, and each table column is a field.

        :param logger: Logging object to display debug/info/error to the logs
            (logs will not be accessible via airbyte UI if they are not passed to this logger)
        :param config: Json object containing the configuration of this source, content of this json is as specified in
        the properties of the spec.json file

        :return: AirbyteCatalog is an object describing a list of all available streams in this source.
            A stream is an AirbyteStream object that includes:
            - its stream name (or table name in the case of Postgres)
            - json_schema providing the specifications of expected schema for this stream (a list of columns described
            by their names and types)
        """
        streams = []
        dirname = os.path.dirname(os.path.realpath(__file__))

        # Fake Users
        spec_path = os.path.join(dirname, "users_catalog.json")
        catalog = read_json(spec_path)
        streams.append(AirbyteStream(name="Users", json_schema=catalog, supported_sync_modes=["full_refresh", "incremental"]))

        # Fake Products
        spec_path = os.path.join(dirname, "products_catalog.json")
        catalog = read_json(spec_path)
        streams.append(AirbyteStream(name="Products", json_schema=catalog, supported_sync_modes=["full_refresh"]))

        # Fake Purchases
        spec_path = os.path.join(dirname, "purchases_catalog.json")
        catalog = read_json(spec_path)
        streams.append(AirbyteStream(name="Purchases", json_schema=catalog, supported_sync_modes=["full_refresh", "incremental"]))

        return AirbyteCatalog(streams=streams)

    def read(
        self, logger: AirbyteLogger, config: Dict[str, any], catalog: ConfiguredAirbyteCatalog, state: Dict[str, any]
    ) -> Generator[AirbyteMessage, None, None]:
        """
        Returns a generator of the AirbyteMessages generated by reading the source with the given configuration,
        catalog, and state.

        :param logger: Logging object to display debug/info/error to the logs
            (logs will not be accessible via airbyte UI if they are not passed to this logger)
        :param config: Json object containing the configuration of this source, content of this json is as specified in
            the properties of the spec.json file
        :param catalog: The input catalog is a ConfiguredAirbyteCatalog which is almost the same as AirbyteCatalog
            returned by discover(), but
        in addition, it's been configured in the UI! For each particular stream and field, there may have been provided
        with extra modifications such as: filtering streams and/or columns out, renaming some entities, etc
        :param state: When a Airbyte reads data from a source, it might need to keep a checkpoint cursor to resume
            replication in the future from that saved checkpoint.
            This is the object that is provided with state from previous runs and avoid replicating the entire set of
            data everytime.

        :return: A generator that produces a stream of AirbyteRecordMessage contained in AirbyteMessage object.
        """

        count: int = config["count"] if "count" in config else 0
        seed: int = config["seed"] if "seed" in config else None
        records_per_sync: int = config["records_per_sync"] if "records_per_sync" in config else 500
        records_per_slice: int = config["records_per_slice"] if "records_per_slice" in config else 100

        Faker.seed(seed)
        fake = Faker()

        to_generate_users = False
        to_generate_purchases = False
        purchases_stream = None
        purchases_count = state["Purchases"]["purchases_count"] if "Purchases" in state else 0
        for stream in catalog.streams:
            if stream.stream.name == "Users":
                to_generate_users = True
        for stream in catalog.streams:
            if stream.stream.name == "Purchases":
                purchases_stream = stream
                to_generate_purchases = True

        if to_generate_purchases and not to_generate_users:
            raise ValueError("Purchases stream cannot be enabled without Users stream")

        for stream in catalog.streams:
            if stream.stream.name == "Users":
                cursor = get_stream_cursor(state, stream.stream.name)
                total_records = cursor
                records_in_sync = 0
                records_in_page = 0

                for i in range(cursor, count):
                    user = generate_user(fake, i)
                    yield generate_record(stream, user)
                    total_records += 1
                    records_in_sync += 1
                    records_in_page += 1

                    if to_generate_purchases:
                        purchases = generate_purchases(fake, user, purchases_count)
                        for p in purchases:
                            yield generate_record(purchases_stream, p)
                            purchases_count += 1

                    if records_in_page == records_per_slice:
                        yield generate_state(state, stream, {"cursor": total_records, "seed": seed})
                        records_in_page = 0

                    if records_in_sync == records_per_sync:
                        break

                yield generate_state(state, stream, {"cursor": total_records, "seed": seed})
                if purchases_stream is not None:
                    yield generate_state(state, purchases_stream, {"purchases_count": purchases_count})

            elif stream.stream.name == "Products":
                products = generate_products()
                for p in products:
                    yield generate_record(stream, p)
                yield generate_state(state, stream, {"product_count": len(products)})

            elif stream.stream.name == "Purchases":
                # Purchases are generated as part of Users stream
                True

            else:
                raise ValueError(stream.stream.name)


def get_stream_cursor(state: Dict[str, any], stream: str) -> int:
    cursor = (state[stream]["cursor"] or 0) if stream in state else 0
    return cursor


def generate_record(stream: any, data: any):
    dict = data.copy()

    # timestamps need to be emitted in ISO format
    for key in dict:
        if isinstance(dict[key], datetime.datetime):
            dict[key] = dict[key].isoformat()

    return AirbyteMessage(
        type=Type.RECORD,
        record=AirbyteRecordMessage(stream=stream.stream.name, data=dict, emitted_at=int(datetime.datetime.now().timestamp()) * 1000),
    )


def generate_state(state: Dict[str, any], stream: any, data: any):
    state[
        stream.stream.name
    ] = data  # since we have multiple streams, we need to build up the "combined state" for all streams and emit that each time until the platform has support for per-stream state
    return AirbyteMessage(type=Type.STATE, state=AirbyteStateMessage(data=state))


def generate_user(fake: Faker, user_id: int):
    profile = fake.profile()
    del profile["birthdate"]  # the birthdate field seems to not obey the seed at the moment, so we'll ignore it

    time_a = fake.date_time()
    time_b = fake.date_time()
    metadata = {
        "id": user_id + 1,
        "created_at": time_a if time_a <= time_b else time_b,
        "updated_at": time_a if time_a > time_b else time_b,
    }
    profile.update(metadata)
    return profile


def generate_purchases(fake: Faker, user: any, purchases_count: int) -> list[Dict]:
    purchases: list[Dict] = []
    purchase_percent_remaining = 80  # ~ 20% of people will have no purchases
    total_products = len(generate_products())
    purchase_percent_remaining = purchase_percent_remaining - random.randrange(1, 100)
    i = 0
    while purchase_percent_remaining > 0:
        id = purchases_count + i + 1
        product_id = random.randrange(1, total_products)
        added_to_cart_at = random_date_in_range(user["created_at"])
        purchased_at = (
            random_date_in_range(added_to_cart_at) if added_to_cart_at is not None and random.randrange(1, 100) <= 70 else None
        )  # 70% likely to purchase the item in the cart
        returned_at = (
            random_date_in_range(purchased_at) if purchased_at is not None and random.randrange(1, 100) <= 15 else None
        )  # 15% likely to return the item
        purchase = {
            "id": id,
            "product_id": product_id,
            "user_id": user["id"],
            "added_to_cart_at": added_to_cart_at,
            "purchased_at": purchased_at,
            "returned_at": returned_at,
        }
        purchases.append(purchase)

        purchase_percent_remaining = purchase_percent_remaining - random.randrange(1, 100)
        i += 1
    return purchases


def generate_products() -> list[Dict]:
    dirname = os.path.dirname(os.path.realpath(__file__))
    return read_json(os.path.join(dirname, "products.json"))


def read_json(filepath):
    with open(filepath, "r") as f:
        return json.loads(f.read())


def random_date_in_range(start_date: datetime.datetime, end_date: datetime.datetime = datetime.datetime.now()) -> datetime.datetime:
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + datetime.timedelta(days=random_number_of_days)
    return random_date