from concurrent import futures
from interceptors.error_interceptor import ErrorInterceptor
from schema.schema_manager import SchemaManager
import time
import math
import logging
import math
import time
from concurrent import futures
import grpc

import proto.messages_pb2 as messages_pb2
import proto.messages_pb2_grpc as messages_pb2_grpc
# from interceptors.error_interceptor import ErrorInterceptor
from config import get_config
from lib.db import Db
from interceptors.auth_interceptor import AuthInterceptor
from services.companies import CompaniesServicer
from services.config import ConfigurationServicer
from services.customers import CustomerServicer
from services.data import DataServicer
from services.reports import ReportServicer
from services.shoes import ShoesServicer
from services.users import UserServicer
import debugpy


class Server():
    def __init__(self, testing = False):
        self.config = get_config()
        self.config['unittesting'] = testing
        if not self.config['staging']:
            with open(self.config['private_key'], 'rb') as f:
                self.private_key = f.read()
            with open(self.config['certificate_chain'], 'rb') as f:
                self.certificate_chain = f.read()

        self.unittesting = testing
        db = Db(self.config['db-host'])
        db.connect()
        self.database = db.get_database('avaclone' if not testing else 'avaclone-unittests')
        SchemaManager(self.database).check_and_update_schema()
    
    def serve(self):
        interceptors = [AuthInterceptor(self.database, self.config)]
        # if not self.config['staging']:
        #     interceptors.append(ErrorInterceptor())
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), interceptors=interceptors)
        messages_pb2_grpc.add_DataServicer_to_server(DataServicer(self.database), server)
        messages_pb2_grpc.add_UsersServicer_to_server(UserServicer(self.database, self.config), server)
        messages_pb2_grpc.add_CustomersServicer_to_server(CustomerServicer(self.database), server)
        messages_pb2_grpc.add_ShoesServicer_to_server(ShoesServicer(self.database), server)
        messages_pb2_grpc.add_CompaniesServicer_to_server(CompaniesServicer(self.database, self.config), server)
        messages_pb2_grpc.add_ConfigurationServicer_to_server(ConfigurationServicer(self.database, self.config), server)
        messages_pb2_grpc.add_ReportsServicer_to_server(ReportServicer(self.database), server)
        server.add_insecure_port('[::]:50051')
        if not self.config['staging']:
            server_credentials = grpc.ssl_server_credentials(((self.private_key, self.certificate_chain,),))
            server.add_secure_port('[::]:50052', server_credentials)
        else:
            debugpy.listen(("localhost", 5678))
        server.start()
        if self.config['staging']:
            print('Server Started')
        
        if not self.unittesting:
            server.wait_for_termination()
        return server


if __name__ == '__main__':
    logging.basicConfig()
    Server().serve()
