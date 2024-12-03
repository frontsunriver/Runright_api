from datetime import datetime
import random

from faker.proxy import Faker
from proto import messages_pb2, messages_pb2_grpc


def insert_test_customer(channel, metadata):
    fake = Faker()
    date = f'{fake.day_of_month()}/{fake.month()}/{fake.year()}'
    date_of_birth = datetime.strptime(date, '%d/%m/%Y').timestamp() * 1000

    # Insert a mock customer
    customer_stub = messages_pb2_grpc.CustomersStub(channel)
    customer_data = {
        'first_name': fake.first_name(),
        'last_name': fake.last_name(),
        'address': fake.address().split('\n'),
        'postcode': fake.postcode(),
        'telephone': fake.phone_number(),
        'email': fake.email(),
        'gender': random.choice([0, 1, 2]),
        'height_mm': random.randint(1650, 1900),
        'weight_g': random.randint(80000, 90000),
        'preferred_speed_metreph': random.randint(5, 20),
        'shoe_size': str(random.randint(5, 14)),
        'date_of_birth': int(date_of_birth)
    }
    message = messages_pb2.Customer(**customer_data)
    resp = customer_stub.setCustomer(message, metadata=metadata)
    customer_id = resp.string_result
    return customer_id, customer_data
