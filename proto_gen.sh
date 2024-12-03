#!/bin/bash
python3 -m grpc_tools.protoc -I avaclone-proto --python_out=proto --grpc_python_out=proto avaclone-proto/messages.proto
sed -i 's/import messages_pb2 as messages__pb2/import proto.messages_pb2 as messages__pb2/g' proto/messages_pb2_grpc.py
