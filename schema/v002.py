from enum import unique
from pymongo.database import Database
from bson import ObjectId
import pymongo

def update(db: Database) -> bool:
    db.shoeTrialResults.create_index([('updated', 1)])
    db.customers.create_index([('updated', 1)])
    return True