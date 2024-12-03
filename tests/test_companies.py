from datetime import datetime
from os import EX_CANTCREAT
from random import choice
from bson import objectid
from bson.objectid import ObjectId
from faker.proxy import Faker
import grpc
from proto import messages_pb2
from services.companies import CompaniesServicer
from tests.test_servicer import TestServicer
from tests.utils.testing_context import TestingContext


class TestCompaniesServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.db.companies.delete_many({})
        self.db.branch_shoes.delete_many({})
        self.servicer = CompaniesServicer(self.db, {})
        self.faker = Faker('en_GB')

    def test_count_companies(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for _ in [6, 5]:
            user_company = choice(companies)
            user_id, user = self.data_generator.generate_fake_user(
                6, user_company[0], choice(user_company[1]))
            request = messages_pb2.CMSQuery()
            context = TestingContext(user)
            count_response = self.servicer.countCompanies(request, context)
            self.assertEqual(count_response.int_result, 4)

    def test_count_companies_no_permission(self):
        for role in [4, 3, 2, 1, 0]:
            user_id, user = self.data_generator.generate_fake_user(role)
            request = messages_pb2.CMSQuery()
            context = TestingContext(user)
            self.assertIsNone(self.servicer.countCompanies(request, context))
            self.assertPermissionDenied(context)

    def test_get_companies(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for _ in [6, 5]:
            user_company = choice(companies)
            user_id, user = self.data_generator.generate_fake_user(
                6, user_company[0], choice(user_company[1]))
            request = messages_pb2.CMSQuery()
            context = TestingContext(user)
            companies_response = list(
                self.servicer.getCompanies(request, context))
            self.assertEqual(len(companies_response), 4)
            self.assertListEqual([x.company_id for x in companies_response], [
                                 x[0] for x in companies])

    def test_get_companies_not_admin(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for role in [4, 3, 2]:
            user_id, user = self.data_generator.generate_fake_user(
                role, choice(companies)[0])
            request = messages_pb2.CMSQuery()
            context = TestingContext(user)
            response = list(self.servicer.getCompanies(request, context))
            self.assertEqual(len(response), 1)
            self.assertEqual(response[0].company_id, user['company_id'])

    def test_get_companies_no_permission(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for role in [1, 0]:
            user_id, user = self.data_generator.generate_fake_user(
                role, choice(companies)[0])
            request = messages_pb2.CMSQuery()
            context = TestingContext(user)
            self.assertIsNone(self.servicer.getCompanies(request, context))
            self.assertPermissionDenied(context)

    def test_get_branch_admin(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for role in [6, 5]:
            admin_id, admin_user = self.data_generator.generate_fake_user(role)
            for company in companies:
                context = TestingContext(admin_user)
                branch_to_get = choice(company[1])
                query = messages_pb2.CMSQuery(string_query=branch_to_get)
                branch = self.servicer.getBranch(query, context)
                self.assertEqual(branch.branch_id, branch_to_get)

    def test_get_branch_not_admin(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for role in [4, 3, 2]:
            company = choice(companies)
            for branch_id in company[1]:
                user_id, user_obj = self.data_generator.generate_fake_user(
                    role, company[0], branch_id)
                context = TestingContext(user_obj)
                for branch_to_get in company[1]:
                    query = messages_pb2.CMSQuery(string_query=branch_to_get)
                    branch = self.servicer.getBranch(query, context)
                    self.assertEqual(branch.branch_id, branch_to_get)

    def test_get_branch_no_permission(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        for role in [4, 3, 2]:
            user_company = choice(companies)
            for company_to_get in [x for x in companies if x != user_company]:
                for branch in company_to_get[1]:
                    user_id, user_obj = self.data_generator.generate_fake_user(
                        role, user_company[0], choice(user_company[1]))
                    context = TestingContext(user_obj)
                    query = messages_pb2.CMSQuery(string_query=branch)
                    branch = self.servicer.getBranch(query, context)
                    self.assertIsNone(branch)
                    self.assertEqual(context.status_code,
                                     grpc.StatusCode.NOT_FOUND)
                    self.assertEqual(
                        context.detail, 'Could not find a branch with the specified ID')

    def test_add_company(self):
        for role in [6, 5]:
            company_data = {
                'name': self.faker.company(),
                'contact_name': self.faker.name(),
                'phone_number': self.faker.phone_number(),
                'email_address': self.faker.email(),
                'address': self.faker.address().split()
            }
            company = messages_pb2.Company(**company_data)
            admin_id, admin_user = self.data_generator.generate_fake_user(role)
            context = TestingContext(admin_user)
            response = self.servicer.addCompany(company, context)
            company_doc = self.db.companies.find_one(
                {'_id': ObjectId(response.string_result)})
            self.assertFalse(company_doc['blocked'])
            self.assertEqual(company_doc['name'], company_data['name'])
            self.assertEqual(
                company_doc['contact_name'], company_data['contact_name'])
            self.assertEqual(
                company_doc['phone_number'], company_data['phone_number'])
            self.assertEqual(
                company_doc['email_address'], company_data['email_address'])
            self.assertEqual(company_doc['branches'], [])

    def test_add_company_no_permission(self):
        for role in [4, 3, 2, 1, 0]:
            company_data = {
                'name': self.faker.company(),
                'contact_name': self.faker.name(),
                'phone_number': self.faker.phone_number(),
                'email_address': self.faker.email(),
                'address': self.faker.address().split()
            }
            company = messages_pb2.Company(**company_data)
            admin_id, admin_user = self.data_generator.generate_fake_user(role)
            context = TestingContext(admin_user)
            self.assertIsNone(self.servicer.addCompany(company, context))
            self.assertPermissionDenied(context)

    def test_edit_company(self):
        self.db.companies.remove({})

        for role in [6, 5]:
            companies = []
            for _ in range(4):
                companies.append(self.data_generator.generate_fake_company(
                    choice([5, 4, 3, 2, 1])))

            for gen_company in companies:
                company_id = gen_company[0]
                admin_id, admin_user = self.data_generator.generate_fake_user(
                    role)
                context = TestingContext(admin_user)
                company = self.servicer.GetCompanyByName(messages_pb2.CMSQuery(string_query=company_id), context)
                company.name = self.faker.company()
                company.email_address = self.faker.email()
                response = self.servicer.editCompany(company, context)
                self.assertTrue(response.int_result)
                company_doc = self.db.companies.find_one(
                    {'_id': ObjectId(company_id)})
                self.assertEqual(company_doc['name'], company.name)
                self.assertEqual(
                    company_doc['email_address'], company.email_address)

    def test_edit_company_no_permission(self):
        companies = []
        for _ in range(4):
            companies.append(self.data_generator.generate_fake_company(
                choice([5, 4, 3, 2, 1])))

        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(admin_user)

        for gen_company in companies:
            company_id = gen_company[0]
            for role in [3, 2, 1, 0]:
                original_company_doc = self.db.companies.find_one(
                    {'_id': ObjectId(company_id)})
                user_id, user = self.data_generator.generate_fake_user(role)
                context = TestingContext(user)
                company = next(self.servicer.getCompanies(
                    messages_pb2.CMSQuery(string_query=company_id), admin_context))
                company.name = self.faker.company()
                company.email_address = self.faker.email()
                self.assertIsNone(self.servicer.editCompany(company, context))
                self.assertPermissionDenied(context)

    def test_add_branch(self):
        company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(admin_user)
        branch_data = {
            'name': self.faker.city(),
            'contact_name': self.faker.name(),
            'phone_number': self.faker.phone_number(),
            'email_address': self.faker.email(),
            'address': self.faker.address().split(),
            'company_id': company_id
        }
        branch = messages_pb2.Branch(**branch_data)
        result = self.servicer.addBranch(branch, admin_context)
        self.assertTrue(result.string_result)
        company = self.db.companies.find_one({'_id': ObjectId(company_id)})
        self.assertEqual(len(company['branches']), 5)

    def test_edit_branch(self):
        company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
        admin_id, admin_user = self.data_generator.generate_fake_user(6)
        admin_context = TestingContext(admin_user)
        branch = self.servicer.getBranch(messages_pb2.CMSQuery(string_query=choice(branch_ids)), admin_context)
        branch.name = self.faker.company()
        branch.email_address = self.faker.email()
        response = self.servicer.editBranch(branch, admin_context)
        self.assertTrue(response.int_result)
        company_doc = self.db.companies.find_one({'_id': ObjectId(company_id)})
        found = False
        for x in company_doc['branches']:
            if x['branch_id'] == branch.branch_id:
                self.assertEqual(x['name'], branch.name)
                self.assertEqual(x['email_address'], branch.email_address)
                found = True
        self.assertTrue(found)

    def test_edit_branch_differing_company(self):
        company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
        user_id, user = self.data_generator.generate_fake_user(4)
        context = TestingContext(user)
        branch = self.servicer.getBranch(messages_pb2.CMSQuery(string_query=context.user['branch_id']), context)
        branch.name = self.faker.company()
        branch.email_address = self.faker.email()
        branch.branch_id = choice(branch_ids)
        response = self.servicer.editBranch(branch, context)
        self.assertFalse(response.int_result)
        company_doc = self.db.companies.find_one({'_id': ObjectId(company_id)})
        for x in company_doc['branches']:
            if x['branch_id'] == branch.branch_id:
                self.assertNotEqual(x['name'], branch.name)
                self.assertNotEqual(x['email_address'], branch.email_address)

    def test_add_branch_differing_company(self):
        company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
        branch_user_id, branch_office_user = self.data_generator.generate_fake_user(4)
        user_context = TestingContext(branch_office_user)
        branch_data = {
            'name': self.faker.city(),
            'contact_name': self.faker.name(),
            'phone_number': self.faker.phone_number(),
            'email_address': self.faker.email(),
            'address': self.faker.address().split(),
            'company_id': company_id
        }
        branch = messages_pb2.Branch(**branch_data)
        result = self.servicer.addBranch(branch, user_context)
        self.assertPermissionDenied(user_context)
        company = self.db.companies.find_one({'_id': ObjectId(company_id)})
        self.assertEqual(len(company['branches']), 4)

    def test_edit_branch_no_permission(self):
        for role in [3,2,1,0]:
            company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
            user_id, user = self.data_generator.generate_fake_user(role)
            user_context = TestingContext(user)
            branch = messages_pb2.Branch()
            response = self.servicer.editBranch(branch, user_context)
            self.assertIsNone(response)
            self.assertPermissionDenied(user_context)

    def test_add_branch_no_permission(self):
        for role in [4,3,2,1,0]:
            company_id, branch_ids = self.data_generator.generate_fake_company(no_branches=4)
            user_id, user = self.data_generator.generate_fake_user(role)
            context = TestingContext(user)
            branch_data = {
                'name': self.faker.city(),
                'contact_name': self.faker.name(),
                'phone_number': self.faker.phone_number(),
                'email_address': self.faker.email(),
                'address': self.faker.address().split(),
                'company_id': company_id
            }
            branch = messages_pb2.Branch(**branch_data)
            result = self.servicer.addBranch(branch, context)
            self.assertIsNone(result)
            self.assertPermissionDenied(context)
