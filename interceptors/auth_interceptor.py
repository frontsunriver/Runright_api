from grpc_interceptor import ServerInterceptor
import grpc
import jwt
from bson import ObjectId

class AuthInterceptor(ServerInterceptor):
    EXEMPT_METHODS = ['/AvaProtos.Users/login', '/AvaProtos.Users/sendPasswordReset', '/AvaProtos.Users/resetPassword']

    def __init__(self, database, config):
        self.config = config
        self.db = database

    def intercept(self, method, request, context, method_name: str):
        user = None
        if method_name == '/AvaProtos.Reports/GetData':
            return method(request, context)
            
        if not method_name in self.EXEMPT_METHODS:
            # Get dict of metadata
            metadict = dict(context.invocation_metadata())
            
            try:
                # Attempt to get token
                auth_header = metadict['authorization']
            except KeyError:
                # No auth header found in metadata
                context.abort(grpc.StatusCode.UNAUTHENTICATED, 'No authorization header provided')
                return

            try:
                # Split auth header value to remove get just the token
                token = auth_header.split(' ')[1]
            except IndexError:
                # Unable to split token
                context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Authorization header is malformed')
                return
            
            # Check token is valid
            try:
                user = jwt.decode(token, self.config['jwt-key'], algorithms=["HS256"], verify=True)
                if not user:
                    # Token is invalid
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Authorization token is invalid/expired. Please reauthenticate')
                    return

                user = self.db.users.find_one({'email': user['email']})
                if user['locked']:
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, 'This account has been locked')
                    return

                if user['role'] < 5:
                    company = self.db.companies.find_one({'_id': ObjectId(user['company_id'])})
                    if company['blocked']:
                        context.abort(grpc.StatusCode.UNAUTHENTICATED, 'This account is blocked. Please contact your RUNRIGHT representative')
                        return
                
            except:
                context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Authorization token is invalid/expired. Please reauthenticate')
                return


            if 'x-grpc-web' in metadict and user['role'] < 3:
                context.abort(grpc.StatusCode.UNAUTHENTICATED, 'Access method not permitted')
                return

        setattr(context, 'user', user)
        return method(request, context)
