import grpc

def check_role(roles):
    def decorator(function):
        def wrapper(instance, request, context):
            if isinstance(roles, list):
                if not context.user['role'] in roles:
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to perform this action')
                    return
            else:
                if not context.user['role'] == roles:
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to perform this action')
                    return
            result = function(instance, request, context)
            return result
        return wrapper
    return decorator

def check_user_role(roles, context):
    if isinstance(roles, list):
        if not context.user['role'] in roles:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to perform this action')
            return
    else:
        if not context.user['role'] == roles:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'You do not have permission to perform this action')
            return