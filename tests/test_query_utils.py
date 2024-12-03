from datetime import datetime
from unittest.case import skip
from pymongo.cursor import Cursor
from pymongo.mongo_client import MongoClient
from lib.timestamp import now
from proto.messages_pb2 import CMSQuery
from lib.query_utils import add_creation_attrs, add_update_attrs, cms_to_mongo, restrict_to_company, skip_and_limit
from unittest import TestCase
from bson import ObjectId
from tests.utils.test_data import MockDataGenerator
from tests.utils.testing_context import TestingContext
from freezegun import freeze_time

class MockCursor():
    def __init__(self):
        self._skip = None
        self._limit = None

    def skip(self, skip_int):
        self._skip = skip_int

    def limit(self, limit_int):
        self._limit = limit_int

class  TestQueryUtils(TestCase):
    def setUp(self) -> None:
        conn = MongoClient()
        db = conn.get_database('avaclone-unittests')
        db.users.remove({})
        db.branch_shoes.remove({})

    def test_cms_query_to_mongo_query(self):
        request = CMSQuery(start_millis=12, end_millis=28)
        query = cms_to_mongo(request)
        self.assertDictEqual(query, {'created': {'$lte': 28, '$gte': 12}})

    def test_cms_query_to_mongo_query_no_start(self):
        request = CMSQuery(start_millis=0, end_millis=300)
        query = cms_to_mongo(request)
        self.assertDictEqual(query, {'created': {'$lte': 300}})

    def test_cms_query_to_mongo_query_no_end(self):
        request = CMSQuery(start_millis=1000)
        query = cms_to_mongo(request)
        self.assertDictEqual(query, {'created': {'$gte': 1000}})

    def test_restrict_to_company(self):
        query = {}
        company_id = ObjectId()
        context = TestingContext(user={'company_id': company_id, 'role': 4})
        restrict_to_company(query, context)
        self.assertEqual(query['company_id'], company_id)

        query = {}
        company_id = ObjectId()
        context = TestingContext(user={'company_id': company_id, 'role': 6})
        restrict_to_company(query, context)
        self.assertEqual(query, {})

    @freeze_time(datetime(2020, 10, 1, 1, 1, 1, 1))
    def test_add_updated_attrs(self):
        data = {}
        generator = MockDataGenerator()
        user_id, user = generator.generate_fake_user(0)
        context = TestingContext(user=user)
        add_update_attrs(data, context)
        self.assertEqual(data['updater'], context.user['email'])
        self.assertEqual(data['updated'], 1601514061000)

    @freeze_time(datetime(2020, 10, 1, 1, 1, 1, 1))
    def test_add_creation_attrs(self):
        data = {}
        generator = MockDataGenerator()
        user_id, user = generator.generate_fake_user(0)
        context = TestingContext(user=user)
        add_creation_attrs(data, context)
        self.assertEqual(data['creator'], context.user['email'])
        self.assertEqual(data['created'], 1601514061000)

    def test_skip_and_limit_limit_only(self):
        cursor = MockCursor()
        query = CMSQuery(limit=12)
        skip_and_limit(query, cursor)
        self.assertEqual(cursor._limit, 12)

    def test_skip_and_limit_skip_only(self):
        cursor = MockCursor()
        query = CMSQuery(skip=12)
        skip_and_limit(query, cursor)
        self.assertEqual(cursor._skip, 12)

    def test_skip_and_limit_both(self):
        cursor = MockCursor()
        query = CMSQuery(skip=20, limit=30)
        skip_and_limit(query, cursor)
        self.assertEqual(cursor._skip, 20)
        self.assertEqual(cursor._limit, 30)