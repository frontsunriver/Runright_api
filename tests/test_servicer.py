import unittest
import grpc
from pymongo.mongo_client import MongoClient
from tests.utils.test_data import MockDataGenerator
from tests.utils.testing_context import TestingContext


class TestServicer(unittest.TestCase):
    def setUp(self):
        client = MongoClient('127.0.0.1:27017')
        self.db = client.get_database('avaclone-unittests')
        self.data_generator = MockDataGenerator(self.db.name)

    def assertPermissionDenied(self, context: TestingContext):
        self.assertEqual(context.status_code, grpc.StatusCode.PERMISSION_DENIED)
        self.assertEqual(context.detail, 'You do not have permission to perform this action')

    def assertHasCreatorAttrs(self, data, context: TestingContext):
        self.assertTrue(data['created'])
        self.assertEqual(data['creator'], context.user['email'])

    def assertHasUpdaterAttrs(self, data, context: TestingContext):
        self.assertTrue(data['updated'])
        self.assertEqual(data['updater'], context.user['email'])