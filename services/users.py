from datetime import datetime, timedelta
from time import time
from uuid import uuid4
from bson.errors import InvalidId
from lib.emai import send_email
from lib.query_utils import add_creation_attrs, add_update_attrs, cms_to_mongo, restrict_to_company, skip_and_limit, sort_cursor
import proto.messages_pb2_grpc as messages_pb2_grpc
import proto.messages_pb2 as messages_pb2
import grpc
import bcrypt
import jwt
from bson import ObjectId
import bcrypt
from lib.timestamp import now
from lib.converter import protobuf_to_dict
from decorators.required_role import check_role, check_user_role

class UserServicer(messages_pb2_grpc.UsersServicer):
    def __init__(self, db, config):
        self.db = db
        self.config = config

    @check_role([4,5,6])
    def setUser(self, request, context):
        # TODO: Will disabling default fields fix fields not passed by form?
        data = protobuf_to_dict(request, including_default_value_fields=True)
        mongoid = False
        if 'user_id' in data:
            if len(data['user_id']):
                # We're editing an existing user, extract MongoId
                mongoid = ObjectId(data['user_id'])
                # Check user exists
                existing_user = self.db.users.find_one({'_id': mongoid})
                if not existing_user:
                    context.abort(grpc.StatusCode.NOT_FOUND, 'Could not find user with specified id')
                    return
                
                # Check company of user that is being edited
                if context.user['role'] not in [6, 5]:
                    if existing_user['company_id'] != context.user['company_id']:
                        context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to edit this user')
                        return

        if not mongoid:
            # New user, create a new object id
            mongoid = ObjectId()
            add_creation_attrs(data, context)
            if not 'password' in data:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Password must be provided for user creation')
                return
            if not len(data['password']):
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Password cannot be empty for new users')
                return
        else:
            add_update_attrs(data, context)

        data['email'] = data['email'].lower().strip()

        # Ensure company_id is enforced for non-admins
        if context.user['role'] not in [6, 5]:
            data['company_id'] = context.user['company_id']

        # Ensure role does not exceed that of acting user
        if context.user['role'] < data['role']:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have the ability to give this role')
            return

        if 'user_id' in data:
            del data['user_id']

        if len(data['password']):
            data['password'] = bcrypt.hashpw(data['password'].encode('utf8'), bcrypt.gensalt())
        else:
            del data['password']

        if not data['company_id']:
            data['branch_id'] = ''

        # Ensure we have a branch ID on user
        if len(data['branch_id']):
            # Try and parse it into ObjectId
            exists = self.db.companies.count({'_id': ObjectId(data['company_id']), 'branches.branch_id': data['branch_id']})
            if not exists:
                # If invalid, bail
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'branchId is invalid')
                return
        
        if context.user['role'] == 4:
            # Set to user's own branch
            data['branch_id'] = context.user['branch_id']

        data['branch_id'] = str(data['branch_id'])

        res = self.db.users.update_one({'_id': mongoid}, {'$set': data}, True)
        if res.modified_count:
            return messages_pb2.CMSResult()
        elif res.upserted_id:
            return messages_pb2.CMSResult(string_result=str(res.upserted_id))

    def countUsers(self, request: messages_pb2.CMSQuery, context):
        # Get a count of users in the system
        query = cms_to_mongo(request, allowed_filters=['name', 'email'])
        if context.user['role'] not in [6, 5, 2]:
            restrict_to_company(query, context)
        
        count = self.db.users.count(query)
        return messages_pb2.CMSResult(
            int_result=count
        )

    @check_role([6,5,4])
    def removeUser(self, request, context):
        if request.user_id:
            query = {'_id': ObjectId(request.user_id)}

        if context.user['role'] == 4:
            query['company_id'] = context.user['company_id']

        res = self.db.users.delete_one(query)
        return messages_pb2.CMSResult(int_result=int(res.deleted_count))


    @check_role([2,4,5,6])
    def getUsers(self, request, context):
        print(context.user)
        query = cms_to_mongo(request, allowed_filters=['name', 'email'])
        if not context.user['role'] in [6]:
            restrict_to_company(query, context)

        if request.filter_on not in ['name', 'email'] and request.string_query:
            try:
                query['_id'] = ObjectId(request.string_query)
            except InvalidId:
                pass

        if context.user['role'] == 4:
            query['branch_id'] = context.user['branch_id']

        if context.user['role'] == 5:
            query['role'] = {'$in' : [5, 3, 2, 1] } 
        elif context.user['role'] == 2: 
            query['role'] = {'$in' : [2] } 
        else:
            query['role'] = {'$lte' : context.user['role'] } 

        if not self.db.users.count(query):
            context.abort(grpc.StatusCode.NOT_FOUND, 'No results found for this query')
            return

        users = self.db.users.find(query)
        skip_and_limit(request, users)
        sort_cursor(request, users, ['name', 'email', 'created'])

        for x in users:
            # Only allow admins to view all
            # Else only show this company
            if (context.user['role'] in [6, 5, 2]) or (x['company_id'] == context.user['company_id']):
                x['user_id'] = str(x['_id'])
                x['company_id'] = str(x['company_id'])
                del x['_id']
                if 'reset_token' in x:
                    del x['reset_token']
                yield messages_pb2.User(**x)


    def getBranchUsers(self, request, context):
        if not request.string_query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'branch_id is required')
            return
        
        query = {'branch_id': request.string_query}
        restrict_to_company(query, context)
        users = self.db.users.find(query)
        skip_and_limit(request, users)
        for x in users:
            x['user_id'] = str(x['_id'])
            x['company_id'] = str(x['company_id'])
            del x['_id']
            yield messages_pb2.User(**x)
            

    def login(self, request, context):
        # Sanity check for email address
        try:
            request.email = request.email.lower().strip()
        except:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, '1111The username/password is incorrect')
            return

        if not request.email or not len(request.email):
            # Email address not valid
            context.abort(grpc.StatusCode.PERMISSION_DENIED, '2222The username/password is incorrect')
            return

        # Attempt to get user from database
        user = self.db.users.find_one({'email': request.email})
        if not user:
            # No user found
            context.abort(grpc.StatusCode.PERMISSION_DENIED, '3333The username/password is incorrect')
            return

        # Check if disabled or locked
        if user['disabled'] or user['locked']:
            # Account is locked/disabled
            context.abort(grpc.StatusCode.PERMISSION_DENIED, '4444The username/password is incorrect')
            return

        # Verify password
        try: 
            user['password'] = user['password'].decode('utf-8')
        except:
            pass

        metadata = dict(context.invocation_metadata())
        if 'x-grpc-web' in metadata:
            if metadata['x-grpc-web'] and user['role'] < 3:
                context.abort(grpc.StatusCode.PERMISSION_DENIED, 'The username/password is incorrect')
                return

        # --------------------------   update part
        company = self.db.companies.find_one({'_id': ObjectId(str(user['company_id']))})
        user['licence_expiry'] = company.get('licence_expiry', 0)
        # if user['licence_expiry'] == 0 and user['role'] == 3:
        #     context.abort(grpc.StatusCode.PERMISSION_DENIED, 'This user can not join because of subscription')
        #     return

        # if user['licence_expiry'] > 0 and user['role'] == 3:
        #     licence_expiry = company.get('licence_expiry', 0)
        #     licence_expiry_date = datetime.fromtimestamp(licence_expiry / 1000) # Assuming the timestamp is in milliseconds

        #     current_date = datetime.now()

        #     # Check if the licence_expiry_date is earlier than the current date
        #     if licence_expiry_date < current_date:
        #         context.abort(grpc.StatusCode.PERMISSION_DENIED, 'The subscription is expired')
        #         return

        user['type'] = company.get('type', '')
        user['user_id'] = str(user['_id'])
            # Remove _id
        del user['_id']
        # Remove password
        del user['password']
        # Generate JWT Token
        user['company_id'] = str(user['company_id'])
        user['exp'] = datetime.now() + timedelta(hours=8)
        user['token'] = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        del user['updated']
        del user['exp']
        if 'reset_token' in user:
            del user['reset_token']
        user = messages_pb2.User(**user)
        return user
        #------------------------- end part

        # if bcrypt.checkpw(request.password.encode('utf8'), user['password'].encode('utf-8')):
        #     # Convert _id to user_id
        #     user['user_id'] = str(user['_id'])
        #     # Remove _id
        #     del user['_id']
        #     # Remove password
        #     del user['password']
        #     # Generate JWT Token
        #     user['company_id'] = str(user['company_id'])
        #     user['exp'] = datetime.now() + timedelta(hours=8)
        #     user['token'] = jwt.encode(user, self.config['jwt-key'], algorithm="HS256")
        #     del user['updated']
        #     del user['exp']
        #     if 'reset_token' in user:
        #         del user['reset_token']
        #     user = messages_pb2.User(**user)
        #     return user
        # else:
        #     # Password verification failed
        #     context.abort(grpc.StatusCode.PERMISSION_DENIED, 'The username/password is incorrect')
        #     return

    def sendPasswordReset(self, request, context):
        # Sanity check for email address
        try:
            email_to_reset = request.string_query.lower().strip()
        except:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'The username/password is incorrect')
            return
        token = uuid4().hex
        res = self.db.users.update_one({'email': email_to_reset}, {'$set': {'reset_token': {'token': token, 'generated': now()}}})
        if res.modified_count:
            # Send email here
            email_contents = f'Someone requested a password reset for your RUNRIGHT account. Please click the following link in order to reset your password. This link will expire after 3 hours. https://app.runright.io/auth/login?token={token}'
            send_email(email_to_reset, email_contents, 'Password Reset Link')
        
        return messages_pb2.CMSResult()


    def resetPassword(self, request, context):
        user = self.db.users.find_one({'reset_token.token': request.token})
        if not user:
            context.abort(grpc.StatusCode.NOT_FOUND, 'Invalid password reset link')
            return

        cut_off = datetime.fromtimestamp(user['reset_token']['generated'] / 1000) + timedelta(hours=3)
        if (int(cut_off.timestamp()) * 1000) < now():
            context.abort(grpc.StatusCode.NOT_FOUND, 'Password reset link has expired')
            return

        password = bcrypt.hashpw(request.password.encode('utf8'), bcrypt.gensalt())
        self.db.users.update_one({'_id': ObjectId(user['_id'])}, {'$set': {'password': password}})
        self.db.users.update_one({'_id': ObjectId(user['_id'])}, {'$unset': {'reset_token': 1}})
        return messages_pb2.CMSResult()