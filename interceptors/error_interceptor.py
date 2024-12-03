import grpc
from grpc_interceptor import ServerInterceptor
from grpc_interceptor.exceptions import GrpcException


class ErrorInterceptor(ServerInterceptor):

    def intercept(self, method, request, context, method_name: str):
        try:
            return method(request, context)
        except Exception as e:
            if not isinstance(e, GrpcException):    
                context.abort(grpc.StatusCode.UNKNOWN, str(e))
                return