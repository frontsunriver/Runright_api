from datetime import datetime, timedelta
from bson.objectid import ObjectId
import grpc
import jwt
from proto import messages_pb2
from interceptors.auth_interceptor import AuthInterceptor
from tests.test_servicer import TestServicer
from tests.utils.testing_context import TestingContext
from freezegun import freeze_time

class TestAuthInterceptor(TestServicer):
    def setUp(self):
        self.context = TestingContext()
        self.config = {
            'jwt-key': 'fake_jwt_key'
        }
        super().setUp()
        self.db.branch_shoes.remove({})
        
    def test_valid_credentials(self):
        user_id, user = self.data_generator.generate_fake_user(6)
        token = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        self.context.set_token(token)
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/ExampleMethod')
        self.assertIsNone(self.context.detail)
        self.assertIsNone(self.context.status_code)
        self.assertTrue(result)

    def test_missing_credentials(self):
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/ExampleMethod')
        self.assertEqual(self.context.detail, 'No authorization header provided')
        self.assertEqual(self.context.status_code, grpc.StatusCode.UNAUTHENTICATED)
        self.assertIsNone(result)

    def test_malformed_credentials(self):
        self.context.metadata = {'authorization': 'malformed'}
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/ExampleMethod')
        self.assertEqual(self.context.detail, 'Authorization header is malformed')
        self.assertEqual(self.context.status_code, grpc.StatusCode.UNAUTHENTICATED)
        self.assertIsNone(result)

    def test_technician_access_web(self):
        user_id, user = self.data_generator.generate_fake_user(2)
        token = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        self.context.metadata = {'authorization': f'token {token}', 'x-grpc-web': True}
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/ExampleMethod')
        self.assertEqual(self.context.detail, 'Access method not permitted')
        self.assertEqual(self.context.status_code, grpc.StatusCode.UNAUTHENTICATED)
        self.assertIsNone(result)

    def test_exempt_method(self):
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos.Users/login')
        self.assertIsNone(self.context.detail)
        self.assertIsNone(self.context.status_code)
        self.assertTrue(result)

    def test_expired_token(self):
        with freeze_time("2012-01-14"):
            user_id, user = self.data_generator.generate_fake_user(2)
            user['exp'] = datetime.now() + timedelta(hours=8)
            token = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        
        self.context.set_token(token)
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/SecureMethod')
        self.assertEqual(self.context.detail, 'Authorization token is invalid/expired. Please reauthenticate')
        self.assertEqual(self.context.status_code, grpc.StatusCode.UNAUTHENTICATED)
        self.assertIsNone(result)

    def test_locked_account(self):
        user_id, user = self.data_generator.generate_fake_user(2)
        token = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        # Lock the user
        self.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'locked': True}})
        self.context.set_token(token)
        result = AuthInterceptor(self.db, self.config).intercept(lambda a,b : a, messages_pb2.CMSQuery(), self.context, '/AvaProtos/ExampleMethod')
        self.assertEqual(self.context.detail, 'This account has been locked')
        self.assertEqual(self.context.status_code, grpc.StatusCode.PERMISSION_DENIED)
        self.assertIsNone(result)
