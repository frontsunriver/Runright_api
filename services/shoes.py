from decorators.required_role import check_role
from lib.query_utils import add_creation_attrs, add_update_attrs, cms_to_mongo, cms_to_shoeModel, restrict_to_company, skip_and_limit, sort_cursor
import proto.messages_pb2_grpc as messages_pb2_grpc
import proto.messages_pb2 as messages_pb2
import grpc
from bson import ObjectId
from lib.converter import protobuf_to_dict

class ShoesServicer(messages_pb2_grpc.ShoesServicer):
    def __init__(self, db):
        self.db = db

    def getShoe(self, request, context):
        if not request.string_query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Please specify EAN in string_query')
            return
        
        shoe = self.db.shoes.find_one({'ean': request.string_query}, {'branches': 0})
        if not shoe:
            context.abort(grpc.StatusCode.NOT_FOUND, 'No shoe found matching specified EAN')
            return
        
        del shoe['_id']
        return messages_pb2.Shoe(**shoe)

    def getShoes(self, request, context):
        # query = cms_to_mongo(request, allowed_filters=['ean', 'brand', 'model', 'season','gender'])
        query = cms_to_shoeModel(request)
        count = self.db.shoes.count(query)
        if not count:
            context.abort(grpc.StatusCode.NOT_FOUND, 'No results found for this query')
            return

        shoes = self.db.shoes.find(query, {'branches': 0})
        skip_and_limit(request, shoes)
        sort_cursor(request, shoes, ['brand', 'model', 'ean', 'season', 'gender'])

        for x in shoes:
            x['shoe_id'] = str(x['_id'])
            del x['_id']
            yield messages_pb2.Shoe(**x)

    def countShoes(self, request, context):
        # query = cms_to_mongo(request, allowed_filters=['ean', 'brand', 'model', 'season','gender'])
        query = cms_to_shoeModel(request)
        count = self.db.shoes.count(query)
        return messages_pb2.CMSResult(int_result=count)

    def doesEanExist(self, request: messages_pb2.CMSQuery, context):
        if not request.string_query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'Please specify EAN in string_query')
        count = self.db.shoes.count({'ean': request.string_query})
        return messages_pb2.CMSResult(int_result=count)

    @check_role([6,5])
    def setShoe(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        try:
            mongo_id = ObjectId(data['shoe_id'])
            add_update_attrs(data, context)
        except:
            mongo_id = ObjectId()
            add_creation_attrs(data, context)

            if data['ean'] in [x['ean'] for x in self.db.shoes.find({}, {'ean': 1})]:
                context.abort(grpc.StatusCode.ALREADY_EXISTS, 'Duplicate EAN')
                return

        res = self.db.shoes.update_one({'_id': mongo_id}, {'$set': data}, upsert=True)
        if res.modified_count:
            data['_id'] = mongo_id
            return messages_pb2.CMSResult(int_result=res.modified_count)
        elif res.upserted_id:
            return messages_pb2.CMSResult(string_result=str(res.upserted_id))

    @check_role([6])
    def removeShoe(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        try:
            mongo_id = ObjectId(data['shoe_id'])
        except:
            mongo_id = ObjectId()

        res = self.db.shoes.delete_one({'_id': mongo_id})
        return messages_pb2.CMSResult(int_result=int(res.deleted_count))

    def getShoesForBranchId(self, request, context):
        # if len(request.string_query.split('?')) > 1:
        #     parts = request.string_query.split('?')
        #     request.string_query = parts[1]
        #     branch_id = parts[0]
        # else:
        #     branch_id = request.string_query

        # query = cms_to_mongo(request, allowed_filters=['ean', 'brand', 'model', 'season'])
        # query['branches'] = {'$in': [branch_id]}
        # shoes = self.db.shoes.find(query, {'branches': 0})
        # skip_and_limit(request, shoes)
        # sort_cursor(request, shoes, ['brand', 'model', 'ean', 'season'])        
        # # shoes = res['branches'][0]['shoes']
        # for shoe in shoes:
        #     shoe['shoe_id'] = str(shoe['_id'])
        #     del shoe['_id']
        #     yield messages_pb2.Shoe(**shoe)
        branch_id = request.branch_id
        query = cms_to_shoeModel(request)
        query['branches'] = {'$in': [branch_id]}
        shoes = self.db.shoes.find(query, {'branches': 0})
        skip_and_limit(request, shoes)
        sort_cursor(request, shoes, ['brand', 'model', 'ean', 'season', 'gender'])

        for x in shoes:
            x['shoe_id'] = str(x['_id'])
            del x['_id']
            yield messages_pb2.Shoe(**x)

    def getTotalShoesForBranchId(self, request, context):
        branch_id = request.branch

        query = {}
        query['branches'] = {'$in': [branch_id]}
        shoes = self.db.shoes.find(query, {'branches': 0})

        for shoe in shoes:
            shoe['shoe_id'] = str(shoe['_id'])
            del shoe['_id']
            yield messages_pb2.Shoe(**shoe)

    def countShoesForBranchId(self, request, context):
        # if len(request.string_query.split('?')) > 1:
        #     parts = request.string_query.split('?')
        #     request.string_query = parts[1]
        #     branch_id = parts[0]
        # else:
        #     branch_id = request.string_query

        # query = cms_to_mongo(request, allowed_filters=['ean', 'brand', 'model', 'season'])
        # query['branches'] = {'$in': [branch_id]}
        branch_id = request.branch_id
        query = cms_to_shoeModel(request)
        query['branches'] = {'$in': [branch_id]}
        shoes = self.db.shoes.find(query, {'branches': 0})
        res = self.db.shoes.count(query)
        return messages_pb2.CMSResult(int_result=res)

    def setShoesForBranch(self, request, context):
        self.db.shoes.update_many({'branches': {'$in': [request.branch_id]}}, {'$pull': {'branches': request.branch_id}})
        res = self.db.shoes.update_many({'ean': {'$in': list(request.shoe_eans)}}, {'$push': {'branches': request.branch_id}})
        return messages_pb2.CMSResult(int_result=res.modified_count)

    def getShoesForModel(self, request, context):
        brand = request.branch_id

        query = {}
        shoes = self.db.shoes.find({'brand': brand})

        for shoe in shoes:
            shoe['shoe_id'] = str(shoe['_id'])
            del shoe['_id']
            del shoe['branches']
            yield messages_pb2.Shoe(**shoe)

    def getShoeSizeList(self, request, context):
        pipeline = []

        pipeline.append(
            {
                '$group': {
                    '_id': "$shoe_size", 
                }
            }
        )

        results = self.db.shoeTrialResults.aggregate(pipeline)

        for shoe in results:
            if str(shoe['_id']) != '':
                shoe['size'] = str(shoe['_id'])
            del(shoe['_id'])
            yield messages_pb2.Shoe(**shoe)

