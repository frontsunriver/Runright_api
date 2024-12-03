from json import loads
import os
import random

from bson import ObjectId
import grpc
from tests.test_servicer import TestServicer
from tests.utils.test_data import MockDataGenerator
from lib.converter import protobuf_to_dict
from proto import messages_pb2
from services.data import DataServicer

from tests.utils.testing_context import TestingContext


class TestDataServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.servicer = DataServicer(self.db)
        self.db.shoeTrialResults.delete_many({})
        self.db.metricMappings.delete_many({})
        self.db.branch_shoes.remove({})

    def test_get_shoe_trial_results_admin(self):
        """Ensure that admins can get all shoeTrialResults"""
        company_id, company_branch_ids = self.data_generator.generate_fake_company(
            2)
        company_2_id, company_2_branch_ids = self.data_generator.generate_fake_company(
            2)
        technician_id, technician = self.data_generator.generate_fake_user(
            4, company_id, random.choice(company_branch_ids))
        technician_2_id, technician_2 = self.data_generator.generate_fake_user(
            4, company_id, random.choice(company_branch_ids))

        technician_3_id, technician_3 = self.data_generator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))
        technician_4_id, technician_3 = self.data_generator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))

        self.data_generator.generate_and_insert_shoe_trial_results(
            count=5, technician_id=technician_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=5, technician_id=technician_2_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=15, technician_id=technician_3_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=15, technician_id=technician_4_id)

        admin_id, admin = self.data_generator.generate_fake_user(6, None, None)
        # Now check a technician from a different company
        context = TestingContext(
            self.db.users.find_one({'_id': ObjectId(admin_id)}))
        request = messages_pb2.CMSQuery()
        results = self.servicer.getShoeTrialResults(request, context)
        self.assertEqual(len(list(results)), 40)

    def test_get_shoe_trial_results_company_restrictions(self):
        """Ensure that the getShoeTrialResult method enforces a company id if the users role is not 5 or 6"""
        company_id, company_branch_ids = self.data_generator.generate_fake_company(
            2)
        company_2_id, company_2_branch_ids = self.data_generator.generate_fake_company(
            2)
        technician_id, technician = self.data_generator.generate_fake_user(
            4, company_id, random.choice(company_branch_ids))
        technician_2_id, technician_2 = self.data_generator.generate_fake_user(
            4, company_id, random.choice(company_branch_ids))

        technician_3_id, technician_3 = self.data_generator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))
        technician_4_id, technician_4 = self.data_generator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))

        self.data_generator.generate_and_insert_shoe_trial_results(
            count=5, technician_id=technician_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=5, technician_id=technician_2_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=15, technician_id=technician_3_id)
        self.data_generator.generate_and_insert_shoe_trial_results(
            count=15, technician_id=technician_4_id)

        # Check technician from first company
        context = TestingContext(self.db.users.find_one(
            {'_id': ObjectId(technician_id)}))
        request = messages_pb2.CMSQuery()
        results = self.servicer.getShoeTrialResults(request, context)
        count = 0

        for i, x in enumerate(results):
            count = i
            # Ensure we're only receiving the company_id of the technician that's
            # requesting them
            self.assertEqual(x.company_id, str(company_id))
            self.assertIn(x.technician_id, [
                          str(technician_id), str(technician_2_id)])

        self.assertEqual(count + 1, 10)

        # Now check a technician from a different company
        context = TestingContext(self.db.users.find_one(
            {'_id': ObjectId(technician_4_id)}))
        request = messages_pb2.CMSQuery()
        results = self.servicer.getShoeTrialResults(request, context)
        count = 0

        for i, x in enumerate(results):
            count = i
            # Ensure we're only receiving the company_id of the technician that's
            # requesting them
            self.assertEqual(x.company_id, str(company_2_id))
            self.assertIn(x.technician_id, [
                          str(technician_3_id), str(technician_4_id)])

        self.assertEqual(count + 1, 30)

    def test_get_shoe_trial_results_start_end_millis(self):
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 12)
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 15)
        admin_id, admin = self.data_generator.generate_fake_user(6, None, None)
        # Now check a technician from a different company
        context = TestingContext(
            self.db.users.find_one({'_id': ObjectId(admin_id)}))
        request = messages_pb2.CMSQuery(end_millis=13)
        results = self.servicer.getShoeTrialResults(request, context)
        self.assertEqual(len(list(results)), 2)

        request = messages_pb2.CMSQuery(start_millis=13)
        results = self.servicer.getShoeTrialResults(request, context)
        self.assertEqual(len(list(results)), 2)

        request = messages_pb2.CMSQuery(start_millis=7)
        results = self.servicer.getShoeTrialResults(request, context)
        self.assertEqual(len(list(results)), 4)

    def test_delete_shoe_trial_results(self):
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 12)
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 15)
        admin_id, admin = self.data_generator.generate_fake_user(6, None, None)
        # Now check a technician from a different company
        context = TestingContext(
            self.db.users.find_one({'_id': ObjectId(admin_id)}))
        request = messages_pb2.CMSQuery()
        results = list(self.servicer.getShoeTrialResults(request, context))
        record_to_delete = random.choice(results)
        delete_query = messages_pb2.CMSQuery(string_query=record_to_delete.recording_id)
        result = self.servicer.deleteShoeTrialResult(delete_query, context)
        self.assertEqual(result.int_result, 1)

        request = messages_pb2.CMSQuery(start_millis=7)
        results = list(self.servicer.getShoeTrialResults(request, context))
        self.assertEqual(len(results), 3)
        for x in results:
            self.assertNotEqual(x.recording_id, record_to_delete.recording_id)

    def test_delete_shoe_trial_result_permissions(self):
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 12)
        self.data_generator.generate_and_insert_shoe_trial_results(2, None, 15)

        for x in range(5):
            user_id, user = self.data_generator.generate_fake_user(
                x, None, None)
            # Now check a technician from a different company
            context = TestingContext(
                self.db.users.find_one({'_id': ObjectId(user_id)}))
            self.servicer.deleteShoeTrialResult(
                messages_pb2.CMSQuery(string_query=str(ObjectId())), context)
            self.assertPermissionDenied(context)

        for x in range(5, 8):
            user_id, user = self.data_generator.generate_fake_user(
                5, None, None)
            # Now check a technician from a different company
            context = TestingContext(
                self.db.users.find_one({'_id': ObjectId(user_id)}))
            self.servicer.deleteShoeTrialResult(
                messages_pb2.CMSQuery(string_query=str(ObjectId())), context)
            self.assertEqual(context.status_code, None)
            self.assertEqual(context.detail, None)

    def test_get_shoe_trial_result_by_customer_id(self):
        """Ensure that shoe trial results can be retrieved for a given customer_id by technicians from the same company"""
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        # Company 1
        company_1_id, company_1_branch_ids = self.data_generatorerator.generate_fake_company(
            no_branches=2)
        technician_1_id, technician_1 = self.data_generatorerator.generate_fake_user(
            4, company_1_id, random.choice(company_1_branch_ids))

        # Company 2
        company_2_id, company_2_branch_ids = self.data_generatorerator.generate_fake_company(
            no_branches=2)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))
        technician_3_id, technician_3 = self.data_generatorerator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))

        # Customer 1
        customer_1_id = self.data_generatorerator.generate_fake_customer(
            company_1_id)
        customer_1_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=4, technician_id=technician_1_id, customer_id=customer_1_id),

        # Customer 2
        customer_2_id = self.data_generatorerator.generate_fake_customer(
            company_2_id)
        customer_2_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=12, technician_id=technician_2_id, customer_id=customer_2_id)

        # Customer 3
        customer_3_id = self.data_generatorerator.generate_fake_customer(
            company_2_id)
        customer_3_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=3, technician_id=technician_2_id, customer_id=customer_3_id)

        # Attempt to get the results for customer 2 using tech 2's creds
        request = messages_pb2.CMSQuery(string_query=str(customer_2_id))
        customer_2_response = list(self.servicer.getShoeTrialResultsByCustomerId(
            request, TestingContext(user=technician_2)))
        customer_2_response_ids = [str(x.recording_id)
                                   for x in customer_2_response]
        self.assertEqual(len(customer_2_response), 12)

        for response in customer_2_response:
            self.assertEqual(response.customer_id, customer_2_id)
            self.assertEqual(response.company_id, company_2_id)
            self.assertEqual(response.technician_id, technician_2_id)
            self.assertIn(response.recording_id, customer_2_response_ids)

        # Check that all responses are returned as expected
        for created_id in customer_2_results:
            self.assertIn(str(created_id), customer_2_response_ids)

        # Attept to get the results of customer 1 using tech 1's creds
        request = messages_pb2.CMSQuery(string_query=str(customer_1_id))
        customer_1_response = list(self.servicer.getShoeTrialResultsByCustomerId(
            request, TestingContext(user=technician_1)))
        customer_1_response_ids = [str(x.recording_id)
                                   for x in customer_1_response]
        self.assertEqual(len(customer_1_response), 4)
        for response in customer_1_response:
            self.assertEqual(response.customer_id, customer_1_id)
            self.assertEqual(response.company_id, company_1_id)
            self.assertEqual(response.technician_id, technician_1_id)
            self.assertIn(response.recording_id, customer_1_response_ids)

        # Check that all responses are returned as expected
        for created_id in customer_1_results[0]:
            self.assertIn(str(created_id), customer_1_response_ids)

        # Attempt to get the results of customer 3 using tech 2's creds
        request = messages_pb2.CMSQuery(string_query=str(customer_3_id))
        customer_3_response = list(self.servicer.getShoeTrialResultsByCustomerId(
            request, TestingContext(user=technician_2)))
        customer_3_response_ids = [str(x.recording_id)
                                   for x in customer_3_response]
        self.assertEqual(len(customer_3_response), 3)
        for response in customer_3_response:
            self.assertEqual(response.customer_id, customer_3_id)
            self.assertEqual(response.company_id, company_2_id)
            self.assertEqual(response.technician_id, technician_2_id)
            self.assertIn(response.recording_id, customer_3_response_ids)

        # Check that all responses are returned as expected
        for created_id in customer_3_results:
            self.assertIn(str(created_id), customer_3_response_ids)

        # Attempt to get the results of customer 3, but using a different tech from the same company
        request = messages_pb2.CMSQuery(string_query=str(customer_3_id))
        customer_3_response = list(self.servicer.getShoeTrialResultsByCustomerId(
            request, TestingContext(user=technician_3)))
        customer_3_response_ids = [str(x.recording_id)
                                   for x in customer_3_response]
        self.assertEqual(len(customer_3_response), 3)
        for response in customer_3_response:
            self.assertEqual(response.customer_id, customer_3_id)
            self.assertEqual(response.company_id, company_2_id)
            self.assertEqual(response.technician_id, technician_2_id)
            self.assertIn(response.recording_id, customer_3_response_ids)

    def test_get_shoe_trial_result_by_customer_diff_company(self):
        """Ensure that shoe trial results CANNOT be retrieved by users from a different company"""
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        # Company 1
        company_1_id, company_1_branch_ids = self.data_generatorerator.generate_fake_company(
            no_branches=2)
        technician_1_id, technician_1 = self.data_generatorerator.generate_fake_user(
            4, company_1_id, random.choice(company_1_branch_ids))

        # Company 2
        company_2_id, company_2_branch_ids = self.data_generatorerator.generate_fake_company(
            no_branches=2)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))
        technician_3_id, technician_3 = self.data_generatorerator.generate_fake_user(
            4, company_2_id, random.choice(company_2_branch_ids))

        # Customer 1
        customer_1_id = self.data_generatorerator.generate_fake_customer(
            company_1_id)
        customer_1_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=4, technician_id=technician_1_id, customer_id=customer_1_id),

        # Customer 2
        customer_2_id = self.data_generatorerator.generate_fake_customer(
            company_2_id)
        customer_2_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=12, technician_id=technician_2_id, customer_id=customer_2_id)

        # Customer 3
        customer_3_id = self.data_generatorerator.generate_fake_customer(
            company_2_id)
        customer_3_results = self.data_generatorerator.generate_and_insert_shoe_trial_results(
            count=3, technician_id=technician_2_id, customer_id=customer_3_id)

        # Attempt to get the results of customer 3, but using a different tech from a different company
        request = messages_pb2.CMSQuery(string_query=str(customer_3_id))
        context = TestingContext(user=technician_1)
        customer_3_response = list(
            self.servicer.getShoeTrialResultsByCustomerId(request, context))
        self.assertFalse(customer_3_response)

    def test_set_shoe_trial_result(self):
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        technician_id, technician = self.data_generatorerator.generate_fake_user(
            4)
        shoe_trial_result = self.data_generatorerator.generate_shoe_trial_result_request(
            technician_id)
        device_id = self.db.companies.find_one({'_id': ObjectId(technician['company_id'])}, {
                                               'branches.devices': 1})['branches'][0]['devices'][0]['device_id']
        shoe_trial_result.device_id = device_id
        context = TestingContext(user=technician)
        response = self.servicer.setShoeTrialResult(shoe_trial_result, context)
        inserted_doc = self.db.shoeTrialResults.find_one(
            {'_id': ObjectId(response.string_result)})
        self.assertEqual(inserted_doc['company_id'], technician['company_id'])
        self.assertEqual(inserted_doc['branch_id'], technician['branch_id'])
        self.assertEqual(inserted_doc['technician_id'], technician_id)
        self.assertEqual(inserted_doc['device_id'], device_id)

    def test_set_shoe_trial_result_differing_company_id(self):
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        technician_id, technician = self.data_generatorerator.generate_fake_user(
            4)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4)
        shoe_trial_result = self.data_generatorerator.generate_shoe_trial_result_request(
            technician_id)
        device_id = self.db.companies.find_one({'_id': ObjectId(technician['company_id'])}, {
                                               'branches.devices': 1})['branches'][0]['devices'][0]['device_id']

        # Change the company id to something different
        shoe_trial_result.company_id = technician_2['company_id']
        # Change the branch id to something different
        shoe_trial_result.branch_id = technician_2['branch_id']

        shoe_trial_result.device_id = device_id
        context = TestingContext(user=technician)
        response = self.servicer.setShoeTrialResult(shoe_trial_result, context)
        inserted_doc = self.db.shoeTrialResults.find_one(
            {'_id': ObjectId(response.string_result)})
        self.assertEqual(inserted_doc['company_id'], technician['company_id'])
        self.assertEqual(inserted_doc['branch_id'], technician['branch_id'])
        self.assertEqual(inserted_doc['technician_id'], technician_id)
        self.assertEqual(inserted_doc['device_id'], device_id)

    def test_set_shoe_trial_result_differing_bad_device_id(self):
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        technician_id, technician = self.data_generatorerator.generate_fake_user(
            4)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4)
        shoe_trial_result = self.data_generatorerator.generate_shoe_trial_result_request(
            technician_id)
        device_id = self.db.companies.find_one({'_id': ObjectId(technician_2['company_id'])}, {
                                               'branches.devices': 1})['branches'][0]['devices'][0]['device_id']

        # Change the company id to something different
        shoe_trial_result.company_id = technician_2['company_id']
        # Change the branch id to something different
        shoe_trial_result.branch_id = technician_2['branch_id']

        shoe_trial_result.device_id = device_id
        context = TestingContext(user=technician)
        response = self.servicer.setShoeTrialResult(shoe_trial_result, context)
        self.assertEqual(context.status_code, grpc.StatusCode.INVALID_ARGUMENT)
        self.assertEqual(context.detail, 'specified device_id does not exist')
        self.assertFalse(self.db.shoeTrialResults.count({}))

    def test_set_metric_mapping(self):
        with open(os.path.join('tests', 'json', 'metric_mapping.json'), 'r') as metric_file:
            metric_mapping = loads(metric_file.read())

        user_id, user = self.data_generator.generate_fake_user(6)
        request = messages_pb2.MetricMappingMsg(**metric_mapping)
        request.version = 1
        test_context = TestingContext(user)
        response = self.servicer.setMetricMapping(request, test_context)
        inserted_id = ObjectId(response.string_result)
        out_messages = self.servicer.getMetricMapping(
            messages_pb2.CMSQuery(), test_context)
        for x in out_messages:
            data = protobuf_to_dict(x, including_default_value_fields=True)
            del data['created']
            # in_message.created = int(datetime.utcnow().timestamp() * 1000)
            self.assertDictContainsSubset(data, protobuf_to_dict(
                request, including_default_value_fields=True))

    def test_set_metric_mapping_same_version(self):
        with open(os.path.join('tests', 'json', 'metric_mapping.json'), 'r') as metric_file:
            metric_mapping = loads(metric_file.read())

        request = messages_pb2.MetricMappingMsg(**metric_mapping)
        request.version = 1
        user_id, user = self.data_generator.generate_fake_user(6)
        test_context = TestingContext(user)
        response = self.servicer.setMetricMapping(request, test_context)
        self.assertTrue(response.string_result)
        self.assertIsNone(test_context.detail)
        self.assertIsNone(test_context.status_code)
        response = self.servicer.setMetricMapping(request, test_context)
        self.assertFalse(response)
        self.assertEqual(test_context.detail,
                         'A metric mapping already exists with this version')
        self.assertEqual(test_context.status_code,
                         grpc.StatusCode.ALREADY_EXISTS)

    def test_get_metric_mapping_no_version(self):
        with open(os.path.join('tests', 'json', 'metric_mapping.json'), 'r') as metric_file:
            metric_mapping = loads(metric_file.read())

        user_id, user = self.data_generator.generate_fake_user(6)
        request = messages_pb2.MetricMappingMsg(**metric_mapping)
        test_context = TestingContext(user)
        response = self.servicer.setMetricMapping(request, test_context)
        self.assertFalse(response)
        self.assertEqual(test_context.status_code,
                         grpc.StatusCode.INVALID_ARGUMENT)
        self.assertEqual(test_context.detail, 'Version must be greater than 0')

    def test_get_shoe_trial_results_by_customer_id(self):
        """Test that when passed a customer ID we get all the expected shoeTrialResults"""
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        company_id, company = self.data_generatorerator.generate_fake_company(
            2)
        technician_id, technician = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_3_id, technician_3 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_ids = [technician_id, technician_2_id, technician_3_id]
        technicians = [technician, technician_2, technician_3]
        customer_id = self.data_generatorerator.generate_fake_customer(
            technician['company_id'])
        self.data_generatorerator.generate_and_insert_shoe_trial_results(
            10, technician_id=random.choice(technician_ids), customer_id=customer_id)

        # Add some extra results from another company to ensure we respect company_id
        company_2_id, company_2 = self.data_generatorerator.generate_fake_company(
            2)
        technician_4_id, technician_4 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_2_id)
        self.data_generatorerator.generate_and_insert_shoe_trial_results(
            30, technician_4_id)

        for tech in technicians:
            testing_context = TestingContext(user=tech)
            request = messages_pb2.CMSQuery(string_query=customer_id)
            response = self.servicer.getShoeTrialResultsByCustomerId(
                request, testing_context)
            for i, shoe_trial_result in enumerate(response):
                self.assertEqual(shoe_trial_result.customer_id, customer_id)
                self.assertEqual(shoe_trial_result.company_id,
                                 technician['company_id'])
            self.assertEqual(i+1, 10)

    def test_count_shoe_trial_results_by_customer_id(self):
        """Test that when passed a customer ID we get all the expected shoeTrialResults"""
        self.data_generatorerator = MockDataGenerator(
            database_name='avaclone-unittests')
        company_id, company = self.data_generatorerator.generate_fake_company(
            2)
        technician_id, technician = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_2_id, technician_2 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_3_id, technician_3 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_id)
        technician_ids = [technician_id, technician_2_id, technician_3_id]
        technicians = [technician, technician_2, technician_3]
        customer_id = self.data_generatorerator.generate_fake_customer(
            technician['company_id'])
        self.data_generatorerator.generate_and_insert_shoe_trial_results(
            10, technician_id=random.choice(technician_ids), customer_id=customer_id)

        # Add some extra results from another company to ensure we respect company_id
        company_2_id, company_2 = self.data_generatorerator.generate_fake_company(
            2)
        technician_4_id, technician_4 = self.data_generatorerator.generate_fake_user(
            4, company_id=company_2_id)
        self.data_generatorerator.generate_and_insert_shoe_trial_results(
            30, technician_4_id)

        for tech in technicians:
            testing_context = TestingContext(user=tech)
            request = messages_pb2.CMSQuery(string_query=customer_id)
            response = self.servicer.countShoeTrialResultsByCustomerId(
                request, testing_context)
            self.assertEqual(response.int_result, 10)
