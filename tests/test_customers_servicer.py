import random
from bson.objectid import ObjectId
from faker.proxy import Faker

import grpc
from proto import messages_pb2
from services.customers import CustomerServicer
from tests.test_servicer import TestServicer
from tests.utils.testing_context import TestingContext


class TestCustomersServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.db.customers.delete_many({})
        self.servicer = CustomerServicer(self.db)
        self.fake = Faker()
        self.db.branch_shoes.remove({})

    def test_create_customer(self):
        admin_id, admin = self.data_generator.generate_fake_user(6)
        request = messages_pb2.CMSQuery()
        context = TestingContext(user=admin)
        response = self.servicer.countCustomers(request, context)
        self.assertFalse(response.int_result)

    def test_customer_count_populated_admin(self):
        admin_id, admin = self.data_generator.generate_fake_user(6)
        context = TestingContext(user=admin)

        for x in range(0, 5):
            self.data_generator.generate_fake_customer()

        message = messages_pb2.CMSQuery()
        response = self.servicer.countCustomers(message, context=context)
        self.assertEqual(response.int_result, 5)

    def test_customer_count_populated_company(self):
        for _ in range(10):
            _, user = self.data_generator.generate_fake_user(
                random.choice([0, 1, 2, 3, 4]))
            context = TestingContext(user)

            num_customers = random.randint(2, 25)
            for _ in range(num_customers):
                self.data_generator.generate_fake_customer(user['company_id'])

            for _ in range(random.randint(2, 10)):
                self.data_generator.generate_fake_customer()

            request = messages_pb2.CMSQuery()
            response = self.servicer.countCustomers(request, context)
            self.assertEqual(response.int_result, num_customers)

    def test_create_new_customer(self):
        fake_customer = {
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "address": self.fake.address().split('\n'),
            "postcode": self.fake.postcode(),
            "telephone": self.fake.phone_number(),
            "email": self.fake.email(),
            "gender": random.choice([0, 1, 2]),
            "height_mm": random.randint(1650, 1900),
            "weight_g": random.randint(80000, 90000),
            "preferred_speed_metreph": random.randint(5, 20),
            "shoe_size": str(random.randint(5, 14)),
            "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
        }
        in_message = messages_pb2.Customer()
        for key, value in fake_customer.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)

        admin_id, admin = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(user=admin)
        self.servicer.setCustomer(in_message, context=admin_context)

        query_message = messages_pb2.CMSQuery()
        response = self.servicer.getCustomers(
            query_message, context=admin_context)
        for x in response:
            for key, value in fake_customer.items():
                self.assertEqual(getattr(x, key), value)

    def test_create_customer_not_admin(self):
        for role in range(4, 0, -1):
            self.db.customers.delete_many({})
            user_id, user = self.data_generator.generate_fake_user(role)
            user_context = TestingContext(user=user)

            fake_customer = {
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "address": self.fake.address().split('\n'),
                "postcode": self.fake.postcode(),
                "telephone": self.fake.phone_number(),
                "email": self.fake.email(),
                "gender": random.choice([0, 1, 2]),
                "height_mm": random.randint(1650, 1900),
                "weight_g": random.randint(80000, 90000),
                "preferred_speed_metreph": random.randint(5, 20),
                "shoe_size": str(random.randint(5, 14)),
                "date_of_birth": int(self.fake.date_time().timestamp() * 1000),
                "company_id": str(ObjectId())
            }
            in_message = messages_pb2.Customer()
            for key, value in fake_customer.items():
                if isinstance(value, list):
                    getattr(in_message, key).extend(value)
                else:
                    setattr(in_message, key, value)

            self.servicer.setCustomer(in_message, context=user_context)

            query_message = messages_pb2.CMSQuery()
            response = self.servicer.getCustomers(
                query_message, context=user_context)
            for x in response:
                for key, value in fake_customer.items():
                    if key != 'company_id':
                        self.assertEqual(getattr(x, key), value)
                    else:
                        self.assertEqual(getattr(x, key), user['company_id'])

    def test_update_existing_customer(self):
        user_id, user = self.data_generator.generate_fake_user(6)
        user_context = TestingContext(user=user)
        # First create a customer
        fake_customer = {
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "address": self.fake.address().split('\n'),
            "postcode": self.fake.postcode(),
            "telephone": self.fake.phone_number(),
            "email": self.fake.email(),
            "gender": random.choice([0, 1, 2]),
            "height_mm": random.randint(1650, 1900),
            "weight_g": random.randint(80000, 90000),
            "preferred_speed_metreph": random.randint(5, 20),
            "shoe_size": str(random.randint(5, 14)),
            "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
        }
        in_message = messages_pb2.Customer()
        for key, value in fake_customer.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setCustomer(in_message, user_context)

        # Now try and edit some details
        # Set customer_id to returned string_val from creation
        in_message.customer_id = response.string_result
        new_name = self.fake.first_name()  # Assign a new first_name
        new_phone = self.fake.phone_number()
        in_message.first_name = new_name  # Set on message
        in_message.telephone = new_phone  # Set on message
        response = self.servicer.setCustomer(
            in_message, context=user_context)  # Update customer
        response = self.servicer.getCustomers(
            messages_pb2.CMSQuery(), context=user_context)  # Pull back out
        for x in response:
            # Check name has been updated
            self.assertEqual(getattr(x, 'first_name'), new_name)
            self.assertEqual(getattr(x, 'telephone'), new_phone)

    def test_update_other_company_customer(self):
        user_id, user = self.data_generator.generate_fake_user(3)
        user_context = TestingContext(user=user)
        self.db.customers.delete_many({})
        # First create a customer
        fake_customer = {
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "address": self.fake.address().split('\n'),
            "postcode": self.fake.postcode(),
            "telephone": self.fake.phone_number(),
            "email": self.fake.email(),
            "gender": random.choice([0, 1, 2]),
            "height_mm": random.randint(1650, 1900),
            "weight_g": random.randint(80000, 90000),
            "preferred_speed_metreph": random.randint(5, 20),
            "shoe_size": str(random.randint(5, 14)),
            "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
        }
        in_message = messages_pb2.Customer()
        for key, value in fake_customer.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setCustomer(in_message, user_context)

        # Now try and edit some details
        new_user_id, new_user = self.data_generator.generate_fake_user(3)
        new_user_context = TestingContext(user=new_user)
        # Set customer_id to returned string_val from creation
        in_message.customer_id = response.string_result
        new_name = self.fake.first_name()  # Assign a new first_name
        new_phone = self.fake.phone_number()
        in_message.first_name = new_name  # Set on message
        in_message.telephone = new_phone  # Set on message
        response = self.servicer.setCustomer(
            in_message, context=new_user_context)  # Update customer
        self.assertEqual(new_user_context.status_code,
                         grpc.StatusCode.NOT_FOUND)
        self.assertEqual(new_user_context.detail,
                         'Could not find customer with specified id')

        # Check not edited
        response = self.servicer.getCustomers(
            messages_pb2.CMSQuery(), context=user_context)  # Pull back out
        for x in response:
            # Check name has been updated
            self.assertEqual(getattr(x, 'first_name'),
                             fake_customer['first_name'])
            self.assertEqual(getattr(x, 'telephone'),
                             fake_customer['telephone'])

    def test_update_existing_customer_invalid_id(self):
        user_id, user = self.data_generator.generate_fake_user(3)
        user_context = TestingContext(user=user)
        self.db.customers.delete_many({})
        # First create a customer
        fake_customer = {
            "customer_id": str(ObjectId()),
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "address": self.fake.address().split('\n'),
            "postcode": self.fake.postcode(),
            "telephone": self.fake.phone_number(),
            "email": self.fake.email(),
            "gender": random.choice([0, 1, 2]),
            "height_mm": random.randint(1650, 1900),
            "weight_g": random.randint(80000, 90000),
            "preferred_speed_metreph": random.randint(5, 20),
            "shoe_size": str(random.randint(5, 14)),
            "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
        }
        in_message = messages_pb2.Customer()
        for key, value in fake_customer.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setCustomer(in_message, user_context)
        self.assertIsNone(response)
        self.assertEqual(user_context.status_code, grpc.StatusCode.NOT_FOUND)
        self.assertEqual(user_context.detail,
                         'Could not find customer with specified id')

    def test_remove_customer(self):
        for role in [6, 5, 4]:
            user_id, user = self.data_generator.generate_fake_user(role)
            user_context = TestingContext(user=user)
            self.db.customers.delete_many({})
            # First create a customer
            fake_customer = {
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "address": self.fake.address().split('\n'),
                "postcode": self.fake.postcode(),
                "telephone": self.fake.phone_number(),
                "email": self.fake.email(),
                "gender": random.choice([0, 1, 2]),
                "height_mm": random.randint(1650, 1900),
                "weight_g": random.randint(80000, 90000),
                "preferred_speed_metreph": random.randint(5, 20),
                "shoe_size": str(random.randint(5, 14)),
                "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
            }
            in_message = messages_pb2.Customer()
            for key, value in fake_customer.items():
                if isinstance(value, list):
                    getattr(in_message, key).extend(value)
                else:
                    setattr(in_message, key, value)
            response = self.servicer.setCustomer(in_message, user_context)
            self.assertEqual(self.db.customers.count({}), 1)
            delete_response = self.servicer.removeCustomer(
                in_message, user_context)
            self.assertEqual(delete_response.int_result, 1)
            self.assertEqual(self.db.customers.count({}), 0)

    def test_cannot_remove_if_not_admin(self):
        for role in [3, 2, 1, 0]:
            user_id, user = self.data_generator.generate_fake_user(3)
            user_context = TestingContext(user=user)
            self.db.customers.delete_many({})
            # First create a customer
            fake_customer = {
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "address": self.fake.address().split('\n'),
                "postcode": self.fake.postcode(),
                "telephone": self.fake.phone_number(),
                "email": self.fake.email(),
                "gender": random.choice([0, 1, 2]),
                "height_mm": random.randint(1650, 1900),
                "weight_g": random.randint(80000, 90000),
                "preferred_speed_metreph": random.randint(5, 20),
                "shoe_size": str(random.randint(5, 14)),
                "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
            }
            in_message = messages_pb2.Customer()
            for key, value in fake_customer.items():
                if isinstance(value, list):
                    getattr(in_message, key).extend(value)
                else:
                    setattr(in_message, key, value)
            response = self.servicer.setCustomer(in_message, user_context)
            self.assertEqual(self.db.customers.count({}), 1)
            delete_response = self.servicer.removeCustomer(
                in_message, user_context)
            self.assertIsNone(delete_response)
            self.assertEqual(
                user_context.detail, 'You do not have permission to perform this action')
            self.assertEqual(user_context.status_code,
                             grpc.StatusCode.PERMISSION_DENIED)

    def test_remove_customer_other_company(self):
        user_id, user = self.data_generator.generate_fake_user(3)
        user_context = TestingContext(user=user)
        self.db.customers.delete_many({})
        # First create a customer
        fake_customer = {
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "address": self.fake.address().split('\n'),
            "postcode": self.fake.postcode(),
            "telephone": self.fake.phone_number(),
            "email": self.fake.email(),
            "gender": random.choice([0, 1, 2]),
            "height_mm": random.randint(1650, 1900),
            "weight_g": random.randint(80000, 90000),
            "preferred_speed_metreph": random.randint(5, 20),
            "shoe_size": str(random.randint(5, 14)),
            "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
        }
        in_message = messages_pb2.Customer()
        for key, value in fake_customer.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setCustomer(in_message, user_context)
        self.assertEqual(self.db.customers.count({}), 1)

        # Now try and delete with a diff user
        user_id, user = self.data_generator.generate_fake_user(4)
        user_context = TestingContext(user=user)
        delete_response = self.servicer.removeCustomer(
            in_message, user_context)
        self.assertFalse(delete_response.int_result)
        self.assertEqual(self.db.customers.count({}), 1)

    def test_get_customers_admin(self):
        for _ in range(25):
            user_id, user = self.data_generator.generate_fake_user(3)
            user_context = TestingContext(user=user)
            # First create a customer
            fake_customer = {
                "first_name": self.fake.first_name(),
                "last_name": self.fake.last_name(),
                "address": self.fake.address().split('\n'),
                "postcode": self.fake.postcode(),
                "telephone": self.fake.phone_number(),
                "email": self.fake.email(),
                "gender": random.choice([0, 1, 2]),
                "height_mm": random.randint(1650, 1900),
                "weight_g": random.randint(80000, 90000),
                "preferred_speed_metreph": random.randint(5, 20),
                "shoe_size": str(random.randint(5, 14)),
                "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
            }
            in_message = messages_pb2.Customer()
            for key, value in fake_customer.items():
                if isinstance(value, list):
                    getattr(in_message, key).extend(value)
                else:
                    setattr(in_message, key, value)
            response = self.servicer.setCustomer(in_message, user_context)

        self.assertEqual(self.db.customers.count({}), 25)
        # Now get all customers as admin
        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(user=admin_user)
        user_response = self.servicer.getCustomers(
            messages_pb2.CMSQuery(), admin_context)
        users = list(user_response)
        self.assertEqual(len(users), 25)

    def test_get_customers_not_admin(self):
        for role in [4, 3, 2, 1, 0]:
            company_user_id, company_user = self.data_generator.generate_fake_user(role)
            company_user_context = TestingContext(user=company_user)

            for _ in range(25):
                user_id, user = self.data_generator.generate_fake_user(3)
                user_context = TestingContext(user=user)
                # First create a customer
                fake_customer = {
                    "first_name": self.fake.first_name(),
                    "last_name": self.fake.last_name(),
                    "address": self.fake.address().split('\n'),
                    "postcode": self.fake.postcode(),
                    "telephone": self.fake.phone_number(),
                    "email": self.fake.email(),
                    "gender": random.choice([0, 1, 2]),
                    "height_mm": random.randint(1650, 1900),
                    "weight_g": random.randint(80000, 90000),
                    "preferred_speed_metreph": random.randint(5, 20),
                    "shoe_size": str(random.randint(5, 14)),
                    "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
                }
                in_message = messages_pb2.Customer()
                for key, value in fake_customer.items():
                    if isinstance(value, list):
                        getattr(in_message, key).extend(value)
                    else:
                        setattr(in_message, key, value)
                response = self.servicer.setCustomer(in_message, user_context)

            for _ in range(10):
                fake_customer = {
                    "first_name": self.fake.first_name(),
                    "last_name": self.fake.last_name(),
                    "address": self.fake.address().split('\n'),
                    "postcode": self.fake.postcode(),
                    "telephone": self.fake.phone_number(),
                    "email": self.fake.email(),
                    "gender": random.choice([0, 1, 2]),
                    "height_mm": random.randint(1650, 1900),
                    "weight_g": random.randint(80000, 90000),
                    "preferred_speed_metreph": random.randint(5, 20),
                    "shoe_size": str(random.randint(5, 14)),
                    "date_of_birth": int(self.fake.date_time().timestamp() * 1000)
                }
                in_message = messages_pb2.Customer()
                for key, value in fake_customer.items():
                    if isinstance(value, list):
                        getattr(in_message, key).extend(value)
                    else:
                        setattr(in_message, key, value)
                response = self.servicer.setCustomer(in_message, company_user_context)

            # Company user should only see 10 results
            user_response = self.servicer.getCustomers(
            messages_pb2.CMSQuery(), company_user_context)
            users = list(user_response)
            company_ids = list(set([x.company_id for x in users]))
            self.assertEqual(len(company_ids), 1)
            self.assertEqual(company_ids[0], company_user['company_id'])
            self.assertEqual(len(users), 10)
