from bcrypt import re
from pymongo.cursor import Cursor
from lib.timestamp import now
from proto.messages_pb2 import CMSQuery
import pymongo
import os
import html

def cms_to_mongo(cms_query: CMSQuery, allowed_filters=None, start_end_on='created') -> dict:
    mongo_query = {}
    if cms_query.start_millis:
        mongo_query[start_end_on] = {'$gte': cms_query.start_millis} 

    if cms_query.end_millis:
        if not start_end_on in mongo_query:
            mongo_query[start_end_on] = {}
        mongo_query[start_end_on]['$lte'] = cms_query.end_millis

    if cms_query.filter_on and allowed_filters and cms_query.filter_on in allowed_filters:
            pattern = re.compile(re.escape(cms_query.string_query), re.IGNORECASE)
            mongo_query[cms_query.filter_on] = {'$regex': pattern}
    return mongo_query

def cms_to_shoeModel(cms_query: CMSQuery) -> dict:
    mongo_query = {}
    filter_on = []
    string_query = []
    if len(cms_query.filter_on) > 0:
        filter_on = cms_query.filter_on.split(",")
        string_query = cms_query.string_query.split(",")
    if len(filter_on) > 0:
        for i,filter in enumerate(filter_on):
            pattern = re.compile(re.escape(string_query[i]), re.IGNORECASE)
            mongo_query[filter] = {'$regex': pattern}
    return mongo_query

def cms_to_customerModel(cms_query: CMSQuery) -> dict:
    mongo_query = {}
    filter_on = []
    string_query = []
    if len(cms_query.filter_on) > 0:
        filter_on = cms_query.filter_on.split(",")
        string_query = cms_query.string_query.split(",")
    if len(filter_on) > 0:
        for i,filter in enumerate(filter_on):
            if filter == "shoe_name" or filter == "shoe_brand" or filter == "shoe_size" or filter == "recording_date" or filter == "shoe_season" :
                pattern = re.compile(re.escape(string_query[i]), re.IGNORECASE)
                mongo_query["shoeTrialResults." + filter] = {'$regex': pattern}
            else: 
                pattern = re.compile(re.escape(string_query[i]), re.IGNORECASE)
                mongo_query[filter] = {'$regex': pattern}
    return mongo_query

def restrict_to_company(mongo_query, context):
    if context.user['role'] not in [6]:
        mongo_query['company_id'] = context.user['company_id']
    return mongo_query

def add_creation_attrs(data, context):
    data['created'] = now()
    data['creator'] = context.user['email']

def add_update_attrs(data, context):
    data['updated'] = now()
    data['updater'] = context.user['email']
    if 'created' in data:
        del data['created']

def skip_and_limit(cms_query: CMSQuery, cursor: Cursor):
    if cms_query.limit:
        cursor.limit(cms_query.limit)
    if cms_query.skip:
        cursor.skip(cms_query.skip)

def sort_cursor(cms_query: CMSQuery, cursor: Cursor, allowed_sorts: None):
    if cms_query.sort_by:
        if not cms_query.sort_by in allowed_sorts:
            return
        cursor.sort(cms_query.sort_by, pymongo.ASCENDING if not cms_query.sort_order else pymongo.DESCENDING)

def save_html_to_file(html_string, file_path):
    # Create directory if it doesn't exist
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Escape HTML string
    escaped_html = html.escape(html_string)
    
    # Write escaped HTML string to file
    with open(file_path, 'w') as file:
        file.write(html_string)
    print("HTML file saved successfully at:", file_path)

def convert_to_int(value):
    if value is None:
        return '0'
    else:
        return str(int(value))

def get_recommedation_value(value):
    if 10 >= value and value >= 9 :
        return "A"
    elif value >= 7 and value < 9:
        return "B"
    elif value >= 4 and value < 7:
        return "C"
    else: 
        return "D"