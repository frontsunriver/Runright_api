from datetime import datetime, timedelta
import random
from lib.timestamp import now
from pymongo import MongoClient
from bson import Int64
from lib.converter import protobuf_to_dict
from google.protobuf.json_format import MessageToJson, ParseDict
from bson.json_util import loads

from proto.messages_pb2 import NoSaleReason, PurchaseDecision, ShoeTrialResult

def main():
    client = MongoClient()
    db = client.get_database('avaclone')
    available_technicians = list(db.users.find({'branch_id': {'$ne': ''}}, {'_id': 1, 'company_id': 1, 'branch_id': 1}))

    for recording in db.shoeTrialResults.find({}):
        today = datetime.utcnow()
        specified_day = today - timedelta(days=random.randint(0, 12))
        timestamp = int(specified_day.timestamp()) * 1000
        decision = random.randint(0, 2)
        no_sale_reason = NoSaleReason.Name(random.randint(0, 5)) if decision == 2 else None
        purchase_decision = PurchaseDecision(decision=decision, no_sale_reason=no_sale_reason)
        shoe_brand = random.choice(db.shoes.distinct('brand'))
        possible_models = list(db.shoes.find({'brand': shoe_brand}, {'model': 1}))
        shoe_name = random.choice(possible_models)['model']


        recording['recording_date'] = Int64(timestamp)
        recording['created'] = Int64(timestamp)
        recording['purchase_decision'] = loads(MessageToJson(purchase_decision, True, use_integers_for_enums=True, preserving_proto_field_name=True))
        technician = random.choice(available_technicians)
        recording['technician_id'] = str(technician['_id'])
        recording['company_id'] = technician['company_id']
        recording['branch_id'] = technician['branch_id']
        recording['shoe_brand'] = shoe_brand
        recording['shoe_name'] = shoe_name

        binary_shoe_trial_result = ShoeTrialResult()
        binary_shoe_trial_result.ParseFromString(recording['bin'])
        binary_shoe_trial_result.recording_date = Int64(timestamp)
        binary_shoe_trial_result.created = Int64(timestamp)
        binary_shoe_trial_result.shoe_brand = shoe_brand
        binary_shoe_trial_result.shoe_name = shoe_name
        recording['bin'] = binary_shoe_trial_result.SerializeToString()
        
        db.shoeTrialResults.update_one({'_id': recording['_id']}, {'$set': recording})
        print(recording['purchase_decision'])

if __name__ == '__main__':
    main()
