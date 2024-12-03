import proto.messages_pb2_grpc as messages_pb2_grpc
import proto.messages_pb2 as messages_pb2
from lib.converter import protobuf_to_dict
from decorators.required_role import check_role
import subprocess

class ConfigurationServicer(messages_pb2_grpc.ConfigurationServicer):
    def __init__(self, db, config):
        self.db = db
        self.config = config

    def getCurrentConfigurationSettings(self, request: messages_pb2.CMSQuery, context) -> messages_pb2.ConfigurationSettings:
        db_res = self.db.settings.find_one({'name': 'current'}, {'name': 0, '_id': 0})
        return messages_pb2.ConfigurationSettings(**db_res)

    @check_role([6])
    def setConfigurationSettings(self, request: messages_pb2.ConfigurationSettings, context) -> messages_pb2.CMSResult:
        data = protobuf_to_dict(request, including_default_value_fields=True)
        db_res = self.db.settings.update_one({'name': 'current'}, {'$set': data}, upsert=True)
        return messages_pb2.CMSResult(string_result=str(db_res.upserted_id))
