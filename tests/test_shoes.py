import enum
import random
from bson import ObjectId
import grpc
from tests.test_servicer import TestServicer
from proto import messages_pb2
from services.shoes import ShoesServicer

from tests.utils.testing_context import TestingContext


#  service Shoes {
#   // List all shoes within the system
#   rpc getShoes(CMSQuery) returns (stream Shoe) {}

#   // List shoes for branch_id specified in string_query
#   rpc getShoesForBranchId(CMSQuery) returns (stream Shoe) {}

#   // Check if a EAN specified in string_query exists, int_result 1 indicates exists
#   rpc doesEanExist(CMSQuery) returns (CMSResult) {}
 
#   // Add / Edit a Shoe
#   rpc setShoe(Shoe) returns (CMSResult) {}
 
#   // Count Shoes matching query
#   rpc countShoes(CMSQuery) returns (CMSResult) {}

#   // Count the numbeer of shoes for a given branch_id in string_query
#   rpc countShoesForBranchId(CMSQuery) returns (CMSResult) {}
#  }

class TestShoesServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.db.shoes.delete_many({})
        self.db.companies.delete_many({})
        self.servicer = ShoesServicer(self.db)

    def test_set_shoe(self):
        admin_id, admin = self.data_generator.generate_fake_user(6)
        testing_context = TestingContext(admin)

        # Try and insert a new shoe
        shoe_data = self.data_generator.generate_shoe_dict()
        shoe_request = messages_pb2.Shoe(**shoe_data)
        response = self.servicer.setShoe(shoe_request, testing_context)
        self.assertTrue(response.string_result)
        shoe_doc = self.db.shoes.find_one({'_id': ObjectId(response.string_result)})
        self.assertHasCreatorAttrs(shoe_doc, testing_context)

    def test_set_shoe_dupe(self):
        admin_id, admin = self.data_generator.generate_fake_user(6)
        testing_context = TestingContext(admin)
        self.db.shoes.remove({})

        # Try and insert a new shoe
        shoe_data = self.data_generator.generate_shoe_dict()
        shoe_request = messages_pb2.Shoe(**shoe_data)
        response = self.servicer.setShoe(shoe_request, testing_context)
        self.assertTrue(response.string_result)

        # Insert the same EAN again
        response = self.servicer.setShoe(shoe_request, testing_context)
        self.assertIsNone(response)
        self.assertEqual(testing_context.detail, 'Duplicate EAN')
        self.assertEqual(testing_context.status_code, grpc.StatusCode.ALREADY_EXISTS)
        self.assertEqual(self.db.shoes.count({}), 1)

    def test_set_shoe_no_permission(self):
        for role in range(4,0, -1):
            _, user = self.data_generator.generate_fake_user(role)
            testing_context = TestingContext(user)

            # Try and insert a new shoe
            shoe_data = self.data_generator.generate_shoe_dict()
            shoe_request = messages_pb2.Shoe(**shoe_data)
            response = self.servicer.setShoe(shoe_request, testing_context)
            self.assertPermissionDenied(testing_context)
            self.assertIsNone(response)

    def test_does_ean_exist(self):
        # Insert a shoe
        admin_id, admin = self.data_generator.generate_fake_user(6)
        testing_context = TestingContext(admin)

        # Try and insert a new shoe
        shoe_data = self.data_generator.generate_shoe_dict()
        shoe_request = messages_pb2.Shoe(**shoe_data)
        response = self.servicer.setShoe(shoe_request, testing_context)
        self.assertTrue(response.string_result)

        # Check existing EAN
        ean_exist_request = messages_pb2.CMSQuery(string_query=shoe_request.ean)
        response = self.servicer.doesEanExist(ean_exist_request, testing_context)
        self.assertTrue(response.int_result)

        # Check non-existant EAN
        ean_exist_request = messages_pb2.CMSQuery(string_query=str(ObjectId()))
        response = self.servicer.doesEanExist(ean_exist_request, testing_context)
        self.assertFalse(response.int_result)

    def test_get_shoes(self):
        # Insert some shoes
        admin_id, admin = self.data_generator.generate_fake_user(6, generate_shoes=False)
        
        for _ in range(20):
            testing_context = TestingContext(admin)
            shoe_data = self.data_generator.generate_shoe_dict()
            shoe_request = messages_pb2.Shoe(**shoe_data)
            response = self.servicer.setShoe(shoe_request, testing_context)
        
        self.assertEqual(self.db.shoes.count_documents({}), 20)

        for role in range(6,0,-1):
            user_id, user = self.data_generator.generate_fake_user(role, generate_shoes=False)
            testing_context = TestingContext(user)
            shoes = self.servicer.getShoes(messages_pb2.CMSQuery(), testing_context)
            for i, shoe in enumerate(shoes):
                pass
            self.assertEqual(i+1, 20)

            # Check that limit works
            limit_query = messages_pb2.CMSQuery(limit=12)
            shoes = self.servicer.getShoes(limit_query, testing_context)
            for i,shoe in enumerate(shoes):
                pass
            self.assertEqual(i+1, 12)

    def test_get_shoes_for_branch_id(self):
        user_id, user = self.data_generator.generate_fake_user(4)
        test_context = TestingContext(user)
        res = self.db.shoes.find({'branches': {'$in': [user['branch_id']]}})
        expected_shoes = [x['ean'] for x in res]
        self.assertGreaterEqual(len(expected_shoes), 5) # ensure there's actually shoes to find
        cms_query = messages_pb2.CMSQuery(string_query=user['branch_id'])
        shoes = self.servicer.getShoesForBranchId(cms_query, test_context)
        found_shoes = [shoe.ean for shoe in shoes]
        self.assertCountEqual(expected_shoes, found_shoes)

    def test_get_shoe_for_branch_id(self):
        user_id, user = self.data_generator.generate_fake_user(4)
        test_context = TestingContext(user)
        shoe_count = self.db.shoes.count({'branches': {'$in': [user['branch_id']]}})
        cms_query = messages_pb2.CMSQuery(string_query=user['branch_id'])
        response = self.servicer.countShoesForBranchId(cms_query, test_context)
        self.assertEqual(response.int_result, shoe_count)

    def test_set_shoes_for_branch(self):
        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(admin_user)
        self.db.shoes.remove({})

        eans = set()
        for _ in range(30):
            shoe_data = self.data_generator.generate_shoe_dict()
            shoe_req = messages_pb2.Shoe(**shoe_data)
            eans.update([shoe_req.ean])
            shoe_resp = self.servicer.setShoe(shoe_req, admin_context)
            self.assertTrue(shoe_resp.string_result)
            del shoe_data
        
        eans = list(eans)

        self.assertEqual(len(eans), self.db.shoes.count({'ean': {'$in': list(eans)}}))
        self.assertEqual(30, self.db.shoes.count({}))

        user_id, user = self.data_generator.generate_fake_user(4)
        user_context = TestingContext(user)
        # Choose 10 random shoes from the list
        branch_eans = set(random.choices(eans, k=10))
        # Set the shoes on the branch
        shoe_update_req = messages_pb2.BranchShoeUpdate(branch_id=user['branch_id'], shoe_eans=branch_eans)
        res = self.servicer.setShoesForBranch(shoe_update_req, user_context)
        self.assertTrue(res.int_result)
        
        # Get the shoes for the branch
        branch_shoes = list(self.servicer.getShoesForBranchId(messages_pb2.CMSQuery(string_query=user['branch_id']), user_context))
        returned_shoe_eans = [x.ean for x in branch_shoes]
        self.assertCountEqual(returned_shoe_eans, branch_eans)

    def test_get_shoe(self):
        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(admin_user)

        shoe_entries = []
        for _ in range(30):
            shoe_data = self.data_generator.generate_shoe_dict()
            shoe_req = messages_pb2.Shoe(**shoe_data)
            shoe_entries.append(shoe_data)
            shoe_resp = self.servicer.setShoe(shoe_req, admin_context)
            self.assertTrue(shoe_resp.string_result)

        for _ in range(20):
            shoe_to_get = random.choice(shoe_entries)
            shoe = self.servicer.getShoe(messages_pb2.CMSQuery(string_query=shoe_to_get['ean']), admin_context)
            self.assertEqual(shoe.brand, shoe_to_get['brand'])
            self.assertEqual(shoe.model, shoe_to_get['model'])
            self.assertEqual(shoe.color, shoe_to_get['color'])
            self.assertEqual(shoe.ean, shoe_to_get['ean'])