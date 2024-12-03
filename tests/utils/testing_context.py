
class TestingContext():
    def __init__(self, user=None, token=None):
        self.user = user
        self.status_code = None
        self.detail = None
        if token:
            self.metadata = {'authorization': f'token {token}'}
        else:
            self.metadata = {}

    def set_token(self, token):
        self.metadata = {'authorization': f'token {token}'}

    def abort(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

    def invocation_metadata(self):
        return self.metadata