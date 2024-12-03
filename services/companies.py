import time
from bson.errors import InvalidId
from lib.query_utils import add_creation_attrs, add_update_attrs, cms_to_mongo, skip_and_limit, sort_cursor
from lib.counter import Counters

import grpc
import proto.messages_pb2 as messages_pb2
import proto.messages_pb2_grpc as messages_pb2_grpc
from bson import ObjectId
from lib.converter import protobuf_to_dict
from pymongo.database import Database
from decorators.required_role import check_role
import base64
import os
from datetime import datetime
from lib.ftp import upload_image_to_ftp

class CompaniesServicer(messages_pb2_grpc.CompaniesServicer):
    def __init__(self, db: Database, config):
        self.db = db
        self.config = config

    def _restrict_to_company_object_id(self, query, context):
        if context.user['role'] not in [6]:
            try:
                query['_id'] = ObjectId(context.user['company_id'])
            except InvalidId:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
                return

    def getBranch(self, request: messages_pb2.CMSQuery, context):
        query = {'branches.branch_id': request.string_query}
        self._restrict_to_company_object_id(query, context)
        company = self.db.companies.find_one(query, {'branches.$': 1, 'name':1})
        if company is None:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Could not find a branch with the specified ID')
            return
        branch_obj = company['branches'][0]
        branch_obj['company_id'] = str(company['_id'])
        resp = messages_pb2.Branch(**branch_obj)
        return resp

    def GetCompanyByName(self, request, context):
        if not request.string_query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Please specify company name in string_query')
            return

        try:
            company_id = ObjectId(request.string_query)
            query = {'_id': company_id}
        except InvalidId:
            query = cms_to_mongo(request)
            query['name'] = request.string_query

        self._restrict_to_company_object_id(query, context)
        company = self.db.companies.find_one(query) 
        company['company_id'] = str(company['_id'])
        del company['_id']
        return messages_pb2.Company(**company)
    
    @check_role([6,5,4,2,3])
    def getCompanies(self, request: messages_pb2.CMSQuery, context):
        query = cms_to_mongo(request, allowed_filters=['name'])
        self._restrict_to_company_object_id(query, context)
        companies = self.db.companies.find(query)
        skip_and_limit(request, companies)
        sort_cursor(request, companies, ['name'])
        for x in companies:
            # Convert _id to company_id for message
            x['company_id'] = str(x['_id'])
            del x['_id']
            yield messages_pb2.Company(**x)

    @check_role([6,5,4])
    def countCompanies(self, request: messages_pb2.CMSQuery, context):
        # Get a count of companies in the system
        query = cms_to_mongo(request, allowed_filters=['name'])
        self._restrict_to_company_object_id(query, context)
        count = self.db.companies.count(query)
        return messages_pb2.CMSResult(
            int_result=count
        )

    @check_role([6,5,4])
    def editCompany(self, request, context):
        # Updating company, don't include default vals
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if context.user['role'] not in [6,5] and str(context.user['company_id']) != str(data['company_id']):
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to edit this company')
            return

        try:
            mongoid = ObjectId(data['company_id'])
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
            return
        del data['company_id']
        del data['branches']
        if not self.db.companies.count({'_id': mongoid}):
            context.abort(grpc.StatusCode.NOT_FOUND,
                          'Could not find company with specified id')
            return            
        add_update_attrs(data, context)
        res = self.db.companies.update_one({'_id': mongoid}, {'$set': data})
        return messages_pb2.CMSResult(int_result=res.modified_count)

    @check_role([6])
    def addCompany(self, request: messages_pb2.Customer, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if self.db.companies.count({'name': data['name']}):
            context.abort(grpc.StatusCode.ALREADY_EXISTS, 'A company already exists by this name')
            return

        add_creation_attrs(data, context)
        # data['branches'] = [{
        #     'branch_id': Counters(self.db).get_next_branch_counter(),
        #     'name': 'N/A',
        #     'creator': request.creator
        # }]
        
        res = self.db.companies.insert_one(data)
        resp = messages_pb2.CMSResult(string_result=str(res.inserted_id))
        return resp

    @check_role([6])
    def addLicense(self, request: messages_pb2.Customer, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if context.user['role'] not in [6,5] and str(context.user['company_id']) != str(data['company_id']):
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to edit this company')
            return

        company_id = data['company_id']

        try:
            mongoid = ObjectId(data['company_id'])
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
            return

        del data['company_id']
        del data['branches']

        if not self.db.companies.count({'_id': mongoid}):
            context.abort(grpc.StatusCode.NOT_FOUND,
                          'Could not find company with specified id')
            return            
        add_update_attrs(data, context)
        res = self.db.companies.update_one({'_id': mongoid}, {'$set': {'licence_expiry': data['licence_expiry'], 'month_count': data['month_count'], 'type': data['type'], 'payment_model': data['payment_model']}})

        historyId = ObjectId()
        history = {}
        history['company_id'] = company_id
        history['type'] = data['type']
        history['month'] = data['month_count']
        history['payment_model'] = data['payment_model']
        history['created'] = int(time.time() * 1000)
        insertedRes = self.db.transhistories.update_one({'_id': historyId}, {'$set': history}, True)
        
        return messages_pb2.CMSResult(int_result=res.modified_count)

    @check_role([6])
    def uploadFile(self, request: messages_pb2.Customer, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if context.user['role'] not in [6,5] and str(context.user['company_id']) != str(data['company_id']):
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to edit this company')
            return

        company_id = data['company_id']
        file_name = data['file_name']
        file_content = data['file_content']

        current_datetime = datetime.now()

        # Format it as a string
        timestamp_str = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{timestamp_str}_{file_name}"

        file_bytes = base64.b64decode(file_content)
        filepath = os.path.join('/home/AvaAdmin/data/upload', file_name)

        # Save the file
        with open(filepath, 'wb') as file:
            file.write(file_bytes)
        
        try:
            mongoid = ObjectId(data['company_id'])
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
            return

        del data['company_id']

        if not self.db.companies.count({'_id': mongoid}):
            context.abort(grpc.StatusCode.NOT_FOUND,
                          'Could not find company with specified id')
            return            
        res = self.db.companies.update_one({'_id': mongoid}, {'$set': {'file_name': file_name}})

        print('file saved')

        upload_image_to_ftp(filepath)

        print('file moved')

        return messages_pb2.CMSResult(int_result=0)
 
    @check_role([6])
    def getLicenseHistory(self, request: messages_pb2.LicenseHistoryQuery, context):
        company_id = request.company_id
        histories = self.db.transhistories.find({'company_id': company_id})
        for x in histories:
            del x['_id']
            yield messages_pb2.LicenseHistory(**x)

    @check_role([6,5])
    def addBranch(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if not context.user['role'] in [6,5]:
            company_id = context.user['company_id']
        else:
            company_id = data['company_id']
        del data['company_id']
        add_creation_attrs(data, context)
        data['branch_id'] = Counters(self.db).get_next_branch_counter()

        try:
            res = self.db.companies.update_one({'_id': ObjectId(company_id)}, {'$push': {'branches': data}})
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
            return
        if res.modified_count:
            return messages_pb2.CMSResult(string_result=data['branch_id'])
        else:
            return messages_pb2.CMSResult()

    @check_role([6,5,4])
    def editBranch(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        if not context.user['role'] in [6,5]:
            company_id = context.user['company_id']
        else:
            company_id = data['company_id']
        del data['company_id']

        if not data['branch_id']:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Please specify the branch_id to be updated')
            return

        add_update_attrs(data, context)
        try:
            query = {'_id': ObjectId(company_id), 'branches.branch_id': data['branch_id']}
            res = self.db.companies.update_one(query, {'$set': {'branches.$': data}})
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Invalid company_id specified')
            return
        return messages_pb2.CMSResult(int_result=res.modified_count)

    @check_role([6])
    def deleteCompany(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        try:
            mongo_id = ObjectId(data['company_id'])
        except:
            mongo_id = ObjectId()
        res = self.db.companies.delete_one({'_id': mongo_id})
        self.db.users.delete_many({'company_id': data['company_id']})
        self.db.shoeTrialResults.delete_many({'company_id': data['company_id']})
        self.db.customers.delete_many({'company_id': data['company_id']})
        return messages_pb2.CMSResult(int_result=int(res.deleted_count))