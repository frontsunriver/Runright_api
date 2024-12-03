from datetime import datetime, timedelta
from lib2to3.pytree import generate_matches

from bson.objectid import ObjectId
from lib.converter import protobuf_to_dict
import random
from proto import messages_pb2
from pymongo import MongoClient
from faker import Faker
import bcrypt
from lib.timestamp import now


class MockDataGenerator():
    def __init__(self, database_name='avaclone-unittests'):
        conn = MongoClient('localhost:27017')
        self.db = conn.get_database(database_name)
        self.db.companies.delete_many({})
        self.db.users.delete_many(
            {'email': {'$ne': 'system.admin@testing.com'}})
        self.shoe_sizes = [str(
            x * 0.5) + ' ' + random.choice(['Mens', 'Womens', 'Unisex']) for x in range(8, 27)]
        self.shoes = [
            {'brand': 'Asics', 'name': 'Jelly Gel'},
            {'brand': 'Nike', 'name': 'React Infinity Run FK2'},
            {'brand': 'Under Armour', 'name': 'Flow Velociti Wind'},
            {'brand': 'Adidas', 'name': 'Ultraboost 21'},
            {'brand': 'Nike', 'name': 'Zoom X Invincible Run'},
            {'brand': 'New Balance', 'name': '1080 v11'},
            {'brand': 'Hoka', 'name': 'One One Mach 4'},
            {'brand': 'Brooks', 'name': 'Levitate 4'},
            {'brand': 'Saucony', 'name': 'Guide 14'}
        ]
        self.branch_id = 0
        self.device_id = 0
        self.faker = Faker(['en_gb'])

    def generate_shoe_dict(self, generate_mongo_ids=False) -> messages_pb2.Shoe:
        shoe = {
            'ean': self.faker.ean(length=13),
            'brand': random.choice(['Under Armour', 'Asics', 'Nike', 'New Balance', 'Hoka', 'Brooks', 'Saucony', 'Adidas', 'Puma']),
            'model': self.faker.aba(),
            'color': self.faker.color_name(),
            'season': str(random.randint(1990, 2021)),
            'gender': random.choice(['Mens', 'Womens', 'Unisex']),
            'size': str(random.randint(1,15)),
        }
        if generate_mongo_ids:
            shoe['_id'] = ObjectId()
        return shoe

        # // Shoe model 
        #     message Shoe {
        #     string shoe_id = 1;
        #     string brand = 2;
        #     string model = 3;
        #     string color = 4;
        #     string ean = 5;
        #     string season = 6;
        #     string gender = 7;
        #     string size = 8;
        #     int64 created = 9;
        #     string creator = 10; // Email address of creator
        #     int64 updated = 11;
        #     string updater = 12;
        # }

    def get_branch_id(self) -> str:
        self.branch_id += 1
        return str(self.branch_id).zfill(4)

    def get_device_id(self) -> str:
        self.device_id += 1
        return str(self.device_id).zfill(10)

    def generate_fake_user(self, role, company_id=None, branch_id=None, generate_shoes=True):
        if not company_id:
            company_id, branch_ids = self.generate_fake_company(random.randint(3, 10), generate_shoes)
            branch_id = random.choice(branch_ids)
        else:
            company = self.db.companies.find_one(
                {'_id': ObjectId(company_id)}, {'branches.branch_id': 1})
            branch_ids = [x['branch_id'] for x in company['branches']]
            branch_id = random.choice(branch_ids)

        user = {
            'auth_failures': 0,
            'branch_id': branch_id,
            'created': int(datetime.now().timestamp()),
            'creator': None,
            'disabled': False,
            'email': self.faker.email(),
            'locked': False,
            'name': self.faker.name(),
            'password': bcrypt.hashpw('password'.encode('utf8'), bcrypt.gensalt()),
            'role': role,
            'updated': int(datetime.now().timestamp()),
            'company_id': str(company_id)
        }
        res = self.db.users.insert_one(user)
        user['password'] = str(user['password'])
        user['user_id'] = str(user['_id'])
        user['_id'] = str(user['_id'])
        return str(res.inserted_id), user

    def generate_fake_company(self, no_branches=2, generate_shoes=True):
        license_end = datetime.now() + timedelta(days=30)
        company = {
            'name': self.faker.company(),
            'contact_name': self.faker.name(),
            'phone_number': self.faker.phone_number(),
            'email_address': self.faker.email(),
            'address': self.faker.address().split(),
            'branches': [
                {
                    'branch_id': self.get_branch_id(),
                    'name': self.faker.city(),
                    'contact_name': self.faker.name(),
                    'phone_number': self.faker.phone_number(),
                    'email_address': self.faker.email(),
                    'address': self.faker.address().split(),
                    'devices': [
                        {
                            'device_id': self.get_device_id(),
                            'license_start': int(datetime.now().timestamp()),
                            'license_end': int(license_end.timestamp())
                        } for x in range(0, random.randint(1, 5))
                    ]
                } for x in range(no_branches)
            ],
            'blocked': False
        }
        res = self.db.companies.insert_one(company)
        if generate_shoes:
            for branch in company['branches']:                
                for _ in range(random.randint(5, 50)):
                    shoe = self.generate_shoe_dict(generate_mongo_ids=True)
                    shoe['branches'] = [branch['branch_id']]
                    self.db.shoes.insert_one(shoe)
        return str(res.inserted_id), [x['branch_id'] for x in company['branches']]

    def generate_fake_customer(self, company_id=None):
        if not company_id:
            company_id, company = self.generate_fake_company()

        customer = {
            'address': self.faker.address().split(),
            'created': 0,
            'creator': "",
            'customer_id': '',
            'date_of_birth': random.randint(0, 10000000),
            'email': self.faker.email(),
            'first_name': self.faker.first_name(),
            'last_name': self.faker.last_name(),
            'postcode': self.faker.postcode(),
            'preferred_speed_metreph': int(random.choice(range(0, 20))),
            'shoe_size': random.choice(self.shoe_sizes),
            'telephone': self.faker.phone_number(),
            'updated': 0,
            'updater': '',
            'weight_g': random.choice(range(45000, 100000)),
            'company_id': company_id
        }
        cust = messages_pb2.Customer(**customer)
        dict = protobuf_to_dict(cust, including_default_value_fields=True)
        res = self.db.customers.insert_one(dict)
        return str(res.inserted_id)

    def generate_and_insert_shoe_trial_results(self, count=10, technician_id=None, created=None, customer_id=None):
        created_ids = []

        for x in range(count):
            request = self.generate_shoe_trial_result_request(
                technician_id, created, customer_id)

            serialised = request.SerializeToString()
            data = protobuf_to_dict(
                request, including_default_value_fields=True)

            # Store message encoded in bin attribute
            data['bin'] = serialised
            res = self.db.shoeTrialResults.insert_one(data)
            created_ids.append(str(res.inserted_id))

        return created_ids

    def generate_shoe_trial_result_request(self, technician_id=None, created=None, customer_id=None):
        request = messages_pb2.ShoeTrialResult()
        request.created = now() if not created else created

        # Select random test_data
        # scan_data = random.choice(self.test_data)

        # Random shoe
        random_shoe = random.choice(self.shoes)
        request.shoe_brand = random_shoe['brand']
        request.shoe_name = random_shoe['name']
        request.shoe_size = str(random.choice(self.shoe_sizes))

        # Set random puchase decision
        purchase_dec = {"decision": random.choice([0, 1, 2])}
        if purchase_dec['decision'] == 2:
            purchase_dec['no_sale_reason'] = random.choice(
                [0, 1, 2, 3, 4, 5])
            purchase_dec['notes'] = 'Lorem ipsum'

        purchase_decision = messages_pb2.PurchaseDecision(
            **purchase_dec)
        request.purchase_decision.MergeFrom(purchase_decision)

        # Set technician
        if technician_id:
            technician = self.db.users.find_one(
                {'_id': ObjectId(technician_id)})
            request.technician_id = str(technician_id)
            request.branch_id = technician['branch_id']
            request.company_id = str(technician['company_id'])

        if not customer_id:
            request.customer_id = self.generate_fake_customer(
                str(request.company_id))
        else:
            request.customer_id = str(customer_id)
        return request


if __name__ == '__main__':
    MockDataGenerator().generate()
