import random
from bson.objectid import ObjectId
import jwt
from proto import messages_pb2
from services.users import UserServicer
from tests.test_servicer import TestServicer
from tests.utils.testing_context import TestingContext
from faker import Faker
from freezegun import freeze_time
import grpc

class TestUserServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.db.users.delete_many({})
        self.servicer = UserServicer(self.db, {'jwt-key': 'fake_key'})
        self.fake = Faker()
        self.db.branch_shoes.remove({})

    def test_user_count(self):
        """Ensure that the correct user count is returned from getUserCount, and that the company_id is respected"""
        request = messages_pb2.CMSQuery()
        _, admin = self.data_generator.generate_fake_user(6)
        companies = {}

        # Insert differing counts for each company
        for company_i in range(4):
            company_id, branch_ids = self.data_generator.generate_fake_company(4)
            companies[company_id] = []
            for _ in range((company_i + 1) * 3):
                _, user = self.data_generator.generate_fake_user(
                    2, company_id, None)
                companies[company_id].append(user)

        # Ensure that the users only get their company count
        for i, company_id in enumerate(companies.keys()):
            user = random.choice(companies[company_id])
            context = TestingContext(user=user)
            response = self.servicer.countUsers(request, context)
            self.assertEqual(response.int_result, len(companies[company_id]))

        # Ensure admins can count ALL users
        total_count = self.db.users.count({})
        context = TestingContext(user=admin)
        response = self.servicer.countUsers(request, context)
        self.assertEqual(response.int_result, total_count)

    def test_create_user(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)

        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password()
        }
        in_message = messages_pb2.User()
        for key, value in fake_user.items():
            setattr(in_message, key, value)

        self.servicer.setUser(in_message, admin_context)
        query_message = messages_pb2.CMSQuery()
        response = self.servicer.countUsers(query_message, admin_context)
        self.assertEqual(response.int_result, 2)

        response = self.servicer.getUsers(query_message, admin_context)
        del fake_user['password']
        found = False
        for x in response:
            if getattr(x, 'email') == fake_user['email']:
                found = True
                for key, value in fake_user.items():
                    self.assertEqual(getattr(x, key), value)
                self.assertFalse(x.disabled)
                self.assertFalse(x.locked)
                self.assertTrue(x.password.startswith('$2b$'))
        self.assertTrue(found)

    def test_create_user_company_enforced(self):
        """Ensure that company_id is enforced when non-admin created user"""
        _, company_user = self.data_generator.generate_fake_user(4, None, None)
        _, second_company_user = self.data_generator.generate_fake_user(4, None, None)
        company_context = TestingContext(company_user)

        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2]),
            "name": self.fake.name(),
            "password": self.fake.password(),
            "company_id": second_company_user['company_id']
        }
        in_message = messages_pb2.User()
        for key, value in fake_user.items():
            setattr(in_message, key, value)

        self.servicer.setUser(in_message, company_context)
        query_message = messages_pb2.CMSQuery()
        response = self.servicer.countUsers(query_message, company_context)
        self.assertEqual(response.int_result, 2)

        response = self.servicer.getUsers(query_message, company_context)
        del fake_user['password']
        found = False
        for x in response:
            if getattr(x, 'email') == fake_user['email']:
                found = True
                self.assertEqual(x.company_id, company_user['company_id'])
        self.assertTrue(found)


    @freeze_time("2021-02-21", auto_tick_seconds=15)
    def test_update_existing_user(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        # First create a user
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password()
        }

        in_message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setUser(in_message, context=admin_context)

        # Now try and edit some details
        # Set user_id to returned string_val from creation
        in_message.user_id = response.string_result
        new_name = self.fake.name()  # Assign a new first_name
        in_message.name = new_name  # Set on message
        response = self.servicer.setUser(in_message, context=admin_context)  # Update user
        response = self.servicer.getUsers(messages_pb2.CMSQuery(), context=admin_context)  # Pull back out
        found = False
        for x in response:
            # Check name has been updated
            if getattr(x, 'name') == new_name:
                found = True
                self.assertEqual(getattr(x, 'name'), new_name)
                self.assertTrue(x.updated > x.created)
        self.assertTrue(found)

    def test_only_admins_can_change_user_company(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        company_id, _ = self.data_generator.generate_fake_company(2)
        # First create a user
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password(),
            "company_id": company_id
        }

        in_message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setUser(in_message, context=admin_context)

        
        # Try and edit company_id as a less than admin user
        in_message.user_id = response.string_result
        new_company_id, _ = self.data_generator.generate_fake_company(2)
        in_message.company_id = new_company_id
        query = messages_pb2.CMSQuery(string_query=in_message.user_id)

        _, user = self.data_generator.generate_fake_user(4, company_id, None)
        user_context = TestingContext(user)
        self.servicer.setUser(in_message, user_context)
        for user in self.servicer.getUsers(query, user_context):
            self.assertNotEqual(user.company_id, new_company_id)
            self.assertEqual(user.company_id, company_id)

    def test_technicians_cannot_get_users(self):
        for role in [3,2,1,0]:
            _, user = self.data_generator.generate_fake_user(role, None, None)
            user_context = TestingContext(user)
            query = messages_pb2.CMSQuery()
            self.assertIsNone(self.servicer.getUsers(query, user_context))
            self.assertEqual(user_context.status_code, grpc.StatusCode.PERMISSION_DENIED)
            self.assertEqual(user_context.detail, 'You do not have permission to perform this action')

                

    def test_users_cannot_edit_other_company_users(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        company_id, _ = self.data_generator.generate_fake_company(2)
        # First create a user
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password(),
            "company_id": company_id
        }

        in_message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(in_message, key).extend(value)
            else:
                setattr(in_message, key, value)
        response = self.servicer.setUser(in_message, context=admin_context)

        
        # Try and edit company_id as a less than admin user
        in_message.user_id = response.string_result
        new_company_id, _ = self.data_generator.generate_fake_company(2)
        in_message.company_id = new_company_id

        in_message.name = self.fake.name()
        _, diff_company_user = self.data_generator.generate_fake_user(4)
        test_context = TestingContext(diff_company_user)
        response = self.servicer.setUser(in_message, test_context)
        self.assertFalse(response)
        self.assertEqual(test_context.status_code, grpc.StatusCode.PERMISSION_DENIED)
        self.assertEqual(test_context.detail, 'You do not have permission to edit this user')
        
    def test_update_existing_user_invalid_id(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password()
        }
        message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(message, key).extend(value)
            else:
                setattr(message, key, value)
        message.user_id = str(ObjectId())
        response = self.servicer.setUser(message, context=admin_context)
        self.assertIsNone(response)
        self.assertEqual(admin_context.status_code,
                            grpc.StatusCode.NOT_FOUND)
        self.assertEqual(admin_context.detail, 'Could not find user with specified id')

    def test_login(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        # First create a fake user
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password()
        }
        message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(message, key).extend(value)
            else:
                setattr(message, key, value)
        response = self.servicer.setUser(message, context=admin_context)

        # Now attempt to login
        unauth_context = TestingContext()
        response = self.servicer.login(messages_pb2.Login(email=fake_user['email'], password=fake_user['password']), context=unauth_context)
        # Make sure correct user is returned
        self.assertEqual(response.email, fake_user['email'])
        # Check we get a JWT token back
        self.assertTrue(len(response.token))
        self.assertEqual(jwt.decode(response.token, options={"verify_signature": False})['email'], fake_user['email'])
        # Check password is not returned
        self.assertFalse(len(response.password))

    def test_bad_login(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        # First create a fake user
        fake_user = {
            "email": self.fake.email(),
            "role": random.choice([0, 1, 2, 3, 4, 5, 6]),
            "name": self.fake.name(),
            "password": self.fake.password()
        }
        message = messages_pb2.User()
        for key, value in fake_user.items():
            if isinstance(value, list):
                getattr(message, key).extend(value)
            else:
                setattr(message, key, value)
        response = self.servicer.setUser(message, context=admin_context)

        # Now attempt to login
        unauth_context = TestingContext()
        response = self.servicer.login(messages_pb2.Login(email=fake_user['email'], password=self.fake.password()), context=unauth_context)
        self.assertEqual(unauth_context.status_code,
                            grpc.StatusCode.PERMISSION_DENIED)
        self.assertEqual(unauth_context.detail,
                            'The username/password is incorrect')
        self.assertIsNone(response)