from enum import unique
from pymongo.database import Database
from bson import ObjectId
import pymongo

def update(db: Database) -> bool:
    db.users.create_index([("branch_id", -1)])
    db.users.create_index("company_id")
    db.users.create_index("email", unique=True)

    db.companies.create_index("name", unique=True)
    db.companies.create_index("branches.branch_id")
    db.companies.create_index([("branches.name", 1), ("name", 1)], unique=True)

    db.shoeTrialResults.create_index([('customer.first_name', 1)])
    db.shoeTrialResults.create_index([('customer.last_name', 1)])
    db.shoeTrialResults.create_index([('purchase_decision.decision', 1)])
    db.shoeTrialResults.create_index([('created', 1)])
    db.shoeTrialResults.create_index([('company_id', 1)])
    db.shoeTrialResults.create_index([('branch_id', 1)])
    db.shoeTrialResults.create_index([('technician_id', 1)])
    db.shoeTrialResults.create_index([('customer_id', 1)])

    db.customers.create_index([('first_name', 1)])
    db.customers.create_index([('last_name', 1)])
    db.customers.create_index([('email', 1)], unique=True)
    db.customers.create_index([('date_of_birth', 1)])
    db.customers.create_index([('created', 1)])

    db.shoes.create_index([('brand', 1)])
    db.shoes.create_index([('model', 1)])
    db.shoes.create_index([('ean', 1)], unique=True)
    db.shoes.create_index([('season', 1)])
    db.shoes.create_index([('branches', 1)])

    db.metricMappings.create_index([('version', 1)], unique=True)

    # db.users.update_one({"_id": ObjectId("600f0d4ce24785fbf593d2b3")}, {'$set': {"email": "system.admin@testing.com", "password": "$2b$10$.kLFgFLqz/2z8idQJweZZuLsr8e6T06WL5QuiUBf.ef3j0t1HLtI6", "role": 6, "created": 1611599181, "creator": "system.admin@testing.com", "disabled": False, "authfailures": 0, "locked": False, "token": "", "name": "System Admin"}}, {'upsert': True}) 

    return True
