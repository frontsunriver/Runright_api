import grpc
import proto.messages_pb2 as messages_pb2
import proto.messages_pb2_grpc as messages_pb2_grpc

def run():
   with grpc.insecure_channel('localhost:9999') as channel:
      stub = messages_pb2_grpc.UsersStub(channel)
      response = stub.login(messages_pb2.Login(email='seriousman1994217winter@gmail.com', password = "12345"))
   print("Greeter client received following from server: " + response.email) 
run()