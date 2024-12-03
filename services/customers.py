import bson
from bson.errors import InvalidId
from pymongo.database import Database
from decorators.required_role import check_role
from lib.query_utils import add_creation_attrs, add_update_attrs, cms_to_mongo, restrict_to_company, skip_and_limit, cms_to_customerModel
import proto.messages_pb2_grpc as messages_pb2_grpc
import proto.messages_pb2 as messages_pb2
import grpc
from bson import BSON, ObjectId
from lib.timestamp import now
from lib.converter import protobuf_to_dict
from lib.query_utils import sort_cursor

class CustomerServicer(messages_pb2_grpc.CustomersServicer):
    def __init__(self, db):
        self.db: Database = db

    def getCustomers(self, request, context):
        # query = cms_to_mongo(request, allowed_filters=['first_name', 'last_name', 'email'], start_end_on='updated')

        # if context.user['role'] not in [6,5]:
        #     restrict_to_company(query, context)
        
        # if not self.db.customers.count(query):
        #     context.abort(grpc.StatusCode.NOT_FOUND, 'No results found for this query')
        #     return

        # customers = self.db.customers.find(query)
        # skip_and_limit(request, customers)
        # sort_cursor(request, customers, ['first_name', 'last_name', 'email', 'created', 'updated'])
        if request.mode :
            pipeline = []
            if context.user['role'] not in [6]:
                pipeline.append({
                    '$match': {
                        'company_id': context.user['company_id']
                    }
                })
            if context.user['role'] == 3:
                pipeline.append({
                    '$match': {
                        'branch_id': context.user['branch_id']
                    }
                })
            pipeline.append(
                {
                    "$project": {
                        "_id": {
                            "$toString": "$_id"
                        },
                        "email": "$email",
                        "address": "$address",
                        "first_name": "$first_name",
                        "last_name": "$last_name",
                        "date_of_birth": "$date_of_birth",
                        "company_id": "$company_id",
                        "branch_id": "$branch_id",
                        "gender": "$gender",
                        "updated": "$updated",
                        "created": "$created"
                    }
                }
            )

            pipeline.append({
                '$lookup': {
                    'from': 'shoeTrialResults',
                    'localField': '_id',
                    'foreignField': 'customer_id',
                    'as': 'shoeTrialResults',
                    'pipeline': [
                        {
                            '$project': {
                                '_id': 0,
                                'recording_date': '$recording_date',
                                'shoe_name': '$shoe_name',
                                'shoe_brand': '$shoe_brand',
                                'shoe_size': '$shoe_size',
                                'shoe_season': '$shoe_season'
                            }
                        },
                        {
                            '$sort': {
                                'recording_date': - 1
                            }
                        },
                        {
                            '$group': {
                                '_id': "$customer_id",
                                'recording_date': {
                                    '$first': '$recording_date'
                                },
                                'shoe_name': {
                                    '$first': '$shoe_name'
                                },
                                'shoe_brand': {
                                        '$first': '$shoe_brand'
                                },
                                'shoe_size': {
                                        '$first': '$shoe_size'
                                },
                                'shoe_season': {
                                        '$first': '$shoe_season'
                                }
                            }
                        }
                    ]
                },
            })

            pipeline.append({
                '$unwind': '$shoeTrialResults'
            })

            sort = request.sort_by
            sort_order = request.sort_order
            if len(sort) > 0:
                if sort == "shoe_name" or sort == "shoe_brand" or sort == "shoe_size" or sort == "recording_date" or sort == "shoe_season" :
                    pipeline.append({
                        "$sort": {
                            "shoeTrialResults." + sort: -1 if sort_order == 0 else 1
                        }
                    })
                else: 
                    pipeline.append({
                        "$sort": {
                            sort: -1 if sort_order == 0 else 1
                        }
                    })
            else: 
                pipeline.append({
                    "$sort": {
                        "shoeTrialResults.recording_date": -1
                    }
                })

            filter_on = []
            string_query = []
            match_query = {}
            if len(request.filter_on) > 0:
                filter_on = request.filter_on.split(",")
                string_query = request.string_query.split(",")
            if len(filter_on) > 0:
                query_model = cms_to_customerModel(request)
                matchObj = {}
                matchObj['$match'] = query_model
                pipeline.append(matchObj)

            skip = request.skip
            pipeline.append({
                '$skip': int(skip)
            })

            limit = request.limit
            pipeline.append({
                '$limit': int(limit)
            })

            customers = self.db.customers.aggregate(pipeline)
            for x in customers:
                if x['company_id']: # Check if company_id is not an empty string
                    try:
                        company = self.db.companies.find_one({'_id': ObjectId(x['company_id'])})
                        if company is not None:
                            x['company_name'] = company['name']
                            branch_name = ''
                            for branch in company['branches']:
                                if branch['branch_id'] == x['branch_id']:
                                    branch_name = branch['name']
                            x['branch_name'] = branch_name
                        else:
                            x['company_name'] = ''
                            x['branch_name'] = ''
                    except bson.errors.InvalidId:
                        # Handle the case where company_id is not a valid ObjectId
                        x['company_name'] = ''
                        x['branch_name'] = ''
                else:
                    # Handle the case where company_id is an empty string
                    x['company_name'] = ''
                    x['branch_name'] = ''

                x['customer_id'] = str(x['_id'])
                del x['_id']
                del x['shoeTrialResults']['_id']
                yield messages_pb2.Customer(**x)
        else:
            query = cms_to_mongo(request, allowed_filters=[
                                 'first_name', 'last_name', 'email'], start_end_on='updated')

            if context.user['role'] not in [6]:
                restrict_to_company(query, context)

            # if not self.db.customers.count(query):
            #     context.abort(grpc.StatusCode.NOT_FOUND,
            #                 'No results found for this query')
            #     return

            customers = self.db.customers.find(query)
            skip_and_limit(request, customers)
            sort_cursor(request, customers, [
                        'first_name', 'last_name', 'email', 'date_of_birth', 'created', 'updated'])
            for x in customers:
                x['customer_id'] = str(x['_id'])
                del x['_id']
                yield messages_pb2.Customer(**x)

    def countCustomers(self, request, context):
        # query = cms_to_mongo(request, allowed_filters=['first_name', 'last_name', 'email'], start_end_on='updated')
        # if context.user['role'] not in [6,5]:
        #     restrict_to_company(query, context)
        # count = self.db.customers.count(query)
        if request.mode :
            pipeline = []
            if context.user['role'] not in [6]:
                pipeline.append({
                    '$match': {
                        'company_id': context.user['company_id']
                    }
                })
            if context.user['role'] == 3:
                pipeline.append({
                    '$match': {
                        'branch_id': context.user['branch_id']
                    }
                })
            pipeline.append(
                {
                    "$project": {
                        "_id": {
                            "$toString": "$_id"
                        },
                        "email": "$email",
                        "address": "$address",
                        "first_name": "$first_name",
                        "last_name": "$last_name",
                        "gender": "$gender",
                        "updated": "$updated"
                    }
                }
            )

            pipeline.append({
                '$lookup': {
                    'from': 'company', # The name of the company collection
                    'localField': 'company_id', # The field from the customers collection
                    'foreignField': '_id', # The field from the company collection
                    'as': 'company_info' # The name of the new array field
                }
            })

            pipeline.append({
                '$lookup': {
                    'from': 'shoeTrialResults',
                    'localField': '_id',
                    'foreignField': 'customer_id',
                    'as': 'shoeTrialResults',
                    'pipeline': [
                        {
                            '$project': {
                                                        '_id': 0,
                                'recording_date': '$recording_date',
                                'shoe_name': '$shoe_name',
                                                        'shoe_brand': '$shoe_brand',
                                                        'shoe_size': '$shoe_size',
                                                        'shoe_season': '$shoe_season'
                            }
                        },
                        {
                            '$sort': {
                                'recording_date': - 1
                            }
                        },
                        {
                            '$group': {
                                '_id': "$customer_id",
                                'recording_date': {
                                    '$first': '$recording_date'
                                },
                                'shoe_name': {
                                    '$first': '$shoe_name'
                                },
                                'shoe_brand': {
                                        '$first': '$shoe_brand'
                                },
                                'shoe_size': {
                                        '$first': '$shoe_size'
                                },
                                'shoe_season': {
                                        '$first': '$shoe_season'
                                }
                            }
                        }
                    ]
                },
            })

            pipeline.append({
                '$unwind': '$shoeTrialResults'
            })

            sort = request.sort_by
            sort_order = request.sort_order
            if len(sort) > 0:
                if sort == "shoe_name" or sort == "shoe_brand" or sort == "shoe_size" or sort == "recording_date" or sort == "shoe_season" :
                    pipeline.append({
                        "$sort": {
                            "shoeTrialResults." + sort: -1 if sort_order == 0 else 1
                        }
                    })
                else: 
                    pipeline.append({
                        "$sort": {
                            sort: -1 if sort_order == 0 else 1
                        }
                    })
            else: 
                pipeline.append({
                    "$sort": {
                        "shoeTrialResults.recording_date": 1
                    }
                })

            filter_on = []
            string_query = []
            match_query = {}
            if len(request.filter_on) > 0:
                filter_on = request.filter_on.split(",")
                string_query = request.string_query.split(",")
            if len(filter_on) > 0:
                query_model = cms_to_customerModel(request)
                matchObj = {}
                matchObj['$match'] = query_model
                pipeline.append(matchObj)

            pipeline.append({
                "$group": {
                    "_id": 'null',
                    "count": { "$sum": 1 }
                }
            })

            count = self.db.customers.aggregate(pipeline)
            count_val = 0
            for x in count:
                count_val = x['count']

            return messages_pb2.CMSResult(int_result=count_val)
        else:
            query = cms_to_mongo(request, allowed_filters=['first_name', 'last_name', 'email'], start_end_on='updated')
            if context.user['role'] not in [6,5]:
                restrict_to_company(query, context)
            count = self.db.customers.count(query)
            return messages_pb2.CMSResult(int_result=count)

    @check_role([6,5,4])
    def removeCustomer(self, request, context):
        if request.customer_id:
            query = {'_id': ObjectId(request.customer_id)}
        elif request.email:
            query = {'email': request.email}

        if context.user['role'] == 4:
            query['company_id'] = context.user['company_id']

        res = self.db.customers.delete_one(query)
        return messages_pb2.CMSResult(int_result=int(res.deleted_count))

    def setCustomer(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        mongoid = False
        if 'customer_id' in data:
            if len(data['customer_id']):
                # We're editing an existing user, extract MongoId
                mongoid = ObjectId(data['customer_id'])
                find_filter = {'_id': mongoid}
                if not context.user['role'] in [6, 5]:
                    restrict_to_company(find_filter, context)
                if not self.db.customers.count(find_filter):
                    context.abort(grpc.StatusCode.NOT_FOUND, 'Could not find customer with specified id')
                    return

        if not mongoid:
            # New user, create a new object id
            mongoid = ObjectId()
            add_creation_attrs(data, context)
        else:
            add_update_attrs(data, context)

        if context.user['role'] not in [6, 5]:
            data['company_id'] = context.user['company_id']

        
        res = self.db.customers.update_one({'_id': mongoid}, {'$set': data}, True)
        if res.modified_count:
            self.db.shoeTrialResults.update_many({'customer._id': ObjectId(data['customer_id'])}, {'$set': {'customer': data}})
            return messages_pb2.CMSResult(int_result=res.modified_count)
        elif res.upserted_id:
            return messages_pb2.CMSResult(string_result=str(res.upserted_id))

    def getBioCustomers(self, request, context):
        pipeline = []
        
        pipeline.append(
            {
                "$project": {
                    "_id": {
                        "$toString": "$_id"
                    },
                    "email": "$email",
                    "address": "$address",
                    "first_name": "$first_name",
                    "last_name": "$last_name",
                    "date_of_birth": "$date_of_birth",
                    "company_id": "$company_id",
                    "branch_id": "$branch_id",
                    "gender": "$gender",
                    "updated": "$updated",
                    "created": "$created"
                }
            }
        )

        pipeline.append({
            '$lookup': {
                'from': 'shoeTrialResults',
                'localField': '_id',
                'foreignField': 'customer_id',
                'as': 'shoeTrialResults',
                'pipeline': [
                    {
                        '$project': {
                            '_id': 0,
                            'recording_date': '$recording_date',
                            'shoe_name': '$shoe_name',
                            'shoe_brand': '$shoe_brand',
                            'shoe_size': '$shoe_size',
                            'shoe_season': '$shoe_season'
                        }
                    },
                    {
                        '$sort': {
                            'recording_date': - 1
                        }
                    },
                    {
                        '$group': {
                            '_id': "$customer_id",
                            'recording_date': {
                                '$first': '$recording_date'
                            },
                            'shoe_name': {
                                '$first': '$shoe_name'
                            },
                            'shoe_brand': {
                                    '$first': '$shoe_brand'
                            },
                            'shoe_size': {
                                    '$first': '$shoe_size'
                            },
                            'shoe_season': {
                                    '$first': '$shoe_season'
                            }
                        }
                    }
                ]
            },
        })

        pipeline.append({
            '$unwind': '$shoeTrialResults'
        })

        sort = request.sort_by
        sort_order = request.sort_order
        if len(sort) > 0:
            if sort == "shoe_name" or sort == "shoe_brand" or sort == "shoe_size" or sort == "recording_date" or sort == "shoe_season" :
                pipeline.append({
                    "$sort": {
                        "shoeTrialResults." + sort: -1 if sort_order == 0 else 1
                    }
                })
            else: 
                pipeline.append({
                    "$sort": {
                        sort: -1 if sort_order == 0 else 1
                    }
                })
        else: 
            pipeline.append({
                "$sort": {
                    "shoeTrialResults.recording_date": 1
                }
            })

        filter_on = []
        string_query = []
        match_query = {}
        if len(request.filter_on) > 0:
            filter_on = request.filter_on.split(",")
            string_query = request.string_query.split(",")
        if len(filter_on) > 0:
            query_model = cms_to_customerModel(request)
            matchObj = {}
            matchObj['$match'] = query_model
            pipeline.append(matchObj)

        if request.company:
            pipeline.append({
                '$match': {
                    'company_id': request.company
                }
            })

        if request.start_millis:
            pipeline.append(
                {
                    '$match': {
                        'shoeTrialResults.recording_date': {'$gte': request.start_millis,
                            '$lte': request.end_millis
                        }
                    },
                }
            )

        if request.start_bir_millis:
            pipeline.append(
                {
                    '$match': {
                        'date_of_birth': {'$gte': request.start_bir_millis,
                            '$lte': request.end_bir_millis
                        }
                    }
                }
            )

        if request.gender:
            pipeline.append({
                '$match': {
                    'gender': int(request.gender)
                }
            })

        if request.brand:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_brand': request.brand
                }
            })

        if request.model:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_name': request.model
                }
            })
        
        if request.season:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_season': request.season
                }
            })

        if request.size:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_size': request.size
                }
            })

        skip = request.skip
        pipeline.append({
            '$skip': int(skip)
        })

        limit = request.limit
        pipeline.append({
            '$limit': int(limit)
        })

        customers = self.db.customers.aggregate(pipeline)
        for x in customers:
            if x['company_id']: 
                try:
                    company = self.db.companies.find_one({'_id': ObjectId(x['company_id'])})
                    if company is not None:
                        x['company_name'] = company['name']
                        branch_name = ''
                        for branch in company['branches']:
                            if branch['branch_id'] == x['branch_id']:
                                branch_name = branch['name']
                        x['branch_name'] = branch_name
                    else:
                        x['company_name'] = ''
                        x['branch_name'] = ''
                except bson.errors.InvalidId:
                    x['company_name'] = ''
                    x['branch_name'] = ''
            else:
                x['company_name'] = ''
                x['branch_name'] = ''

            x['customer_id'] = str(x['_id'])
            del x['_id']
            del x['shoeTrialResults']['_id']
            yield messages_pb2.Customer(**x)

    def countBioCustomers(self, request, context):
        pipeline = []

        pipeline.append(
            {
                "$project": {
                    "_id": {
                        "$toString": "$_id"
                    },
                    "email": "$email",
                    "address": "$address",
                    "first_name": "$first_name",
                    "last_name": "$last_name",
                    "date_of_birth": "$date_of_birth",
                    "gender": "$gender",
                    "updated": "$updated",
                    "company_id": "$company_id",
                }
            }
        )

        pipeline.append({
            '$lookup': {
                'from': 'company', # The name of the company collection
                'localField': 'company_id', # The field from the customers collection
                'foreignField': '_id', # The field from the company collection
                'as': 'company_info' # The name of the new array field
            }
        })

        pipeline.append({
            '$lookup': {
                'from': 'shoeTrialResults',
                'localField': '_id',
                'foreignField': 'customer_id',
                'as': 'shoeTrialResults',
                'pipeline': [
                    {
                        '$project': {
                            '_id': 0,
                            'recording_date': '$recording_date',
                            'shoe_name': '$shoe_name',
                            'shoe_brand': '$shoe_brand',
                            'shoe_size': '$shoe_size',
                            'shoe_season': '$shoe_season'
                        }
                    },
                    {
                        '$sort': {
                            'recording_date': - 1
                        }
                    },
                    {
                        '$group': {
                            '_id': "$customer_id",
                            'recording_date': {
                                '$first': '$recording_date'
                            },
                            'shoe_name': {
                                '$first': '$shoe_name'
                            },
                            'shoe_brand': {
                                    '$first': '$shoe_brand'
                            },
                            'shoe_size': {
                                    '$first': '$shoe_size'
                            },
                            'shoe_season': {
                                    '$first': '$shoe_season'
                            }
                        }
                    }
                ]
            },
        })

        pipeline.append({
            '$unwind': '$shoeTrialResults'
        })

        sort = request.sort_by
        sort_order = request.sort_order
        if len(sort) > 0:
            if sort == "shoe_name" or sort == "shoe_brand" or sort == "shoe_size" or sort == "recording_date" or sort == "shoe_season" :
                pipeline.append({
                    "$sort": {
                        "shoeTrialResults." + sort: -1 if sort_order == 0 else 1
                    }
                })
            else: 
                pipeline.append({
                    "$sort": {
                        sort: -1 if sort_order == 0 else 1
                    }
                })
        else: 
            pipeline.append({
                "$sort": {
                    "shoeTrialResults.recording_date": 1
                }
            })

        filter_on = []
        string_query = []
        match_query = {}
        if len(request.filter_on) > 0:
            filter_on = request.filter_on.split(",")
            string_query = request.string_query.split(",")
        if len(filter_on) > 0:
            query_model = cms_to_customerModel(request)
            matchObj = {}
            matchObj['$match'] = query_model
            pipeline.append(matchObj)

        if request.company:
            pipeline.append({
                '$match': {
                    'company_id': request.company
                }
            })

        if request.gender:
            pipeline.append({
                '$match': {
                    'gender': int(request.gender)
                }
            })

        if request.start_millis:
            pipeline.append(
                {
                    '$match': {
                        'shoeTrialResults.recording_date': {'$gte': request.start_millis,
                            '$lte': request.end_millis
                        }
                    },
                }
            )

        if request.start_bir_millis:
            pipeline.append(
                {
                    '$match': {
                        'date_of_birth': {'$gte': request.start_bir_millis,
                            '$lte': request.end_bir_millis
                        }
                    }
                }
            )

        if request.brand:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_brand': request.brand
                }
            })

        if request.model:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_name': request.model
                }
            })
        
        if request.season:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_season': request.season
                }
            })

        if request.size:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_size': request.size
                }
            })

        pipeline.append({
            "$group": {
                "_id": 'null',
                "count": { "$sum": 1 }
            }
        })

        count = self.db.customers.aggregate(pipeline)
        count_val = 0
        for x in count:
            count_val = x['count']

        return messages_pb2.CMSResult(int_result=count_val)
        
    def getBioCustomersExport(self, request, context):
        pipeline = []
        
        pipeline.append(
            {
                "$project": {
                    "_id": {
                        "$toString": "$_id"
                    },
                    "email": "$email",
                    "address": "$address",
                    "first_name": "$first_name",
                    "last_name": "$last_name",
                    "date_of_birth": "$date_of_birth",
                    "company_id": "$company_id",
                    "branch_id": "$branch_id",
                    "gender": "$gender",
                    "updated": "$updated",
                    "created": "$created"
                }
            }
        )

        pipeline.append({
            '$lookup': {
                'from': 'shoeTrialResults',
                'localField': '_id',
                'foreignField': 'customer_id',
                'as': 'shoeTrialResults',
                'pipeline': [
                    {
                        '$project': {
                            '_id': 0,
                            'recording_date': '$recording_date',
                            'shoe_name': '$shoe_name',
                            'shoe_brand': '$shoe_brand',
                            'shoe_size': '$shoe_size',
                            'shoe_season': '$shoe_season',
                            'raw_metrics' : '$raw_metrics',
                            'purchase_decision': '$purchase_decision',
                            # 'right_step_separation' : '$raw_metrics',
                            # 'body_mass_index' : '$raw_metrics',
                            # 'running_speed' : '$raw_metrics',
                            # 'cadence' : '$raw_metrics',
                            # 'right_ground_contact' : '$raw_metrics',
                            # 'left_ground_contact' : '$raw_metrics',
                            # 'avg_ground_contact' : '$raw_metrics',
                            # 'flight_time' : '$raw_metrics',
                            # 'vertical_oscillation' : '$raw_metrics',
                            # 'sideways_oscillation' : '$raw_metrics',
                            # 'forward_oscillation' : '$raw_metrics',
                            # 'dynamic_balance' : '$raw_metrics',
                            # 'stride_length' : '$raw_metrics',
                            # 'left_overstride' : '$raw_metrics',
                            # 'right_overstride' : '$raw_metrics',
                            # 'avg_overstride' : '$raw_metrics',
                            # 'braking_power' : '$raw_metrics',
                            # 'left_knee_stability' : '$raw_metrics',
                            # 'right_knee_stability' : '$raw_metrics',
                            # 'avg_knee_stability' : '$raw_metrics',
                            # 'left_GC_vertical_oscillation' : '$raw_metrics',
                            # 'right_GC_vertical_oscillation' : '$raw_metrics',
                            # 'avg_GC_vertical_oscillation' : '$raw_metrics',
                            # 'left_norm_separation' : '$raw_metrics',
                            # 'right_norm_separation' : '$raw_metrics',
                            # 'avg_normal_separation' : '$raw_metrics',
                            # 'left_knee_angle' : '$raw_metrics',
                            # 'right_knee_angle' : '$raw_metrics',
                            # 'avg_knee_angle' : '$raw_metrics',
                            # 'left_knee_flexion' : '$raw_metrics',
                            # 'right_knee_flexion' : '$raw_metrics',
                            # 'avg_knee_flexion' : '$raw_metrics',
                            # 'vertical_stiffness' : '$raw_metrics',
                            # 'duty_factor' : '$raw_metrics',
                            # 'right_dorsiflexion' : '$raw_metrics',
                            # 'left_orsiflexion' : '$raw_metrics',
                            # 'avg_dorsiflexion' : '$raw_metrics',
                            # 'VOSL_magnitude' : '$raw_metrics',
                        }
                    },
                    {
                        '$sort': {
                            'recording_date': - 1
                        }
                    },
                    {
                        '$group': {
                            '_id': "$customer_id",
                            'recording_date': {
                                '$first': '$recording_date'
                            },
                            'shoe_name': {
                                '$first': '$shoe_name'
                            },
                            'shoe_brand': {
                                    '$first': '$shoe_brand'
                            },
                            'shoe_size': {
                                    '$first': '$shoe_size'
                            },
                            'shoe_season': {
                                    '$first': '$shoe_season'
                            },
                            'raw_metrics': {
                                    '$first': '$raw_metrics'
                            },
                            'purchase_decision': {
                                '$first': '$purchase_decision'
                            }
                        }
                    }
                ]
            },
        })

        pipeline.append({
            '$unwind': '$shoeTrialResults'
        })

        if request.company:
            pipeline.append({
                '$match': {
                    'company_id': request.company
                }
            })

        if request.start_millis:
            pipeline.append(
                {
                    '$match': {
                        'shoeTrialResults.recording_date': {'$gte': request.start_millis,
                            '$lte': request.end_millis
                        }
                    },
                }
            )

        if request.start_bir_millis:
            pipeline.append(
                {
                    '$match': {
                        'date_of_birth': {'$gte': request.start_bir_millis,
                            '$lte': request.end_bir_millis
                        }
                    }
                }
            )

        if request.gender:
            pipeline.append({
                '$match': {
                    'gender': int(request.gender)
                }
            })

        if request.brand:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_brand': request.brand
                }
            })

        if request.model:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_name': request.model
                }
            })
        
        if request.season:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_season': request.season
                }
            })

        if request.size:
            pipeline.append({
                '$match': {
                    'shoeTrialResults.shoe_size': request.size
                }
            })

        def ensure_nested_key_exists(data, keys, default_value):
            if not keys:
                return
            key = keys[0]
            if len(keys) == 1:
                if key not in data:
                    data[key] = default_value
            else:
                if key not in data:
                    data[key] = {}
                ensure_nested_key_exists(data[key], keys[1:], default_value)

        customers = self.db.customers.aggregate(pipeline)
        for x in customers:
            if x['company_id']: 
                try:
                    company = self.db.companies.find_one({'_id': ObjectId(x['company_id'])})
                    if company is not None:
                        x['company_name'] = company['name']
                        branch_name = ''
                        for branch in company['branches']:
                            if branch['branch_id'] == x['branch_id']:
                                branch_name = branch['name']
                        x['branch_name'] = branch_name
                    else:
                        x['company_name'] = ''
                        x['branch_name'] = ''
                except bson.errors.InvalidId:
                    x['company_name'] = ''
                    x['branch_name'] = ''
            else:
                x['company_name'] = ''
                x['branch_name'] = ''

            x['customer_id'] = str(x['_id'])
            

            metrics_keys = [
                ['Left Step Separation', 'median'],
                ['Right Step Separation', 'median'],
                ['Body Mass Index', 'median'],
                ['Running Speed', 'median'],
                ['Cadence', 'median'],
                ['Right Ground Contact', 'median'],
                ['Left Ground Contact', 'median'],
                ['Avg Ground Contact', 'median'],
                ['Flight Time', 'median'],
                ['Vertical Oscillation', 'median'],
                ['Sideways Oscillation', 'median'],
                ['Forward Oscillation', 'median'],
                ['Dynamic Balance', 'median'],
                ['Stride Length', 'median'],
                ['Left Overstride', 'median'],
                ['Right Overstride', 'median'],
                ['Avg Overstride', 'median'],
                ['Braking Power', 'median'],
                ['Left Knee Stability', 'median'],
                ['Right Knee Stability', 'median'],
                ['Avg Knee Stability', 'median'],
                ['Left GC Vertical Oscillation', 'median'],
                ['Right GC Vertical Oscillation', 'median'],
                ['Avg GC Vertical Oscillation', 'median'],
                ['Left Norm Separation', 'median'],
                ['Right Norm Separation', 'median'],
                ['Avg Norm Separation', 'median'],
                ['Left Knee Angle', 'median'],
                ['Right Knee Angle', 'median'],
                ['Avg Knee Angle', 'median'],
                ['Left Knee Flexion', 'median'],
                ['Right Knee Flexion', 'median'],
                ['Avg Knee Flexion', 'median'],
                ['Vertical Stiffness', 'median'],
                ['Duty Factor', 'median'],
                ['Right Dorsiflexion', 'median'],
                ['Left Dorsiflexion', 'median'],
                ['Avg Dorsiflexion', 'median'],
                ['VOSL Magnitude', 'median'],
            ]
            
            # Ensure each key exists and set a default value if not
            for metric_key in metrics_keys:
                ensure_nested_key_exists(x['shoeTrialResults']['raw_metrics'], metric_key, 0)

            x['left_step_separation'] = x['shoeTrialResults']['raw_metrics']['Left Step Separation']['median']
            x['right_step_separation'] = x['shoeTrialResults']['raw_metrics']['Right Step Separation']['median']
            x['body_mass_index'] = x['shoeTrialResults']['raw_metrics']['Body Mass Index']['median']
            x['running_speed'] = x['shoeTrialResults']['raw_metrics']['Running Speed']['median']
            x['cadence'] = x['shoeTrialResults']['raw_metrics']['Cadence']['median']
            x['right_ground_contact'] = x['shoeTrialResults']['raw_metrics']['Right Ground Contact']['median']
            x['left_ground_contact'] = x['shoeTrialResults']['raw_metrics']['Left Ground Contact']['median']
            x['avg_ground_contact'] = x['shoeTrialResults']['raw_metrics']['Avg Ground Contact']['median']
            x['flight_time'] = x['shoeTrialResults']['raw_metrics']['Flight Time']['median']
            x['vertical_oscillation'] = x['shoeTrialResults']['raw_metrics']['Vertical Oscillation']['median']
            x['sideways_oscillation'] = x['shoeTrialResults']['raw_metrics']['Sideways Oscillation']['median']
            x['forward_oscillation'] = x['shoeTrialResults']['raw_metrics']['Forward Oscillation']['median']
            x['dynamic_balance'] = x['shoeTrialResults']['raw_metrics']['Dynamic Balance']['median']
            x['stride_length'] = x['shoeTrialResults']['raw_metrics']['Stride Length']['median']
            x['left_overstride'] = x['shoeTrialResults']['raw_metrics']['Left Overstride']['median']
            x['right_overstride'] = x['shoeTrialResults']['raw_metrics']['Right Overstride']['median']
            x['avg_overstride'] = x['shoeTrialResults']['raw_metrics']['Avg Overstride']['median']
            x['braking_power'] = x['shoeTrialResults']['raw_metrics']['Braking Power']['median']
            x['left_knee_stability'] = x['shoeTrialResults']['raw_metrics']['Left Knee Stability']['median']
            x['right_knee_stability'] = x['shoeTrialResults']['raw_metrics']['Right Knee Stability']['median']
            x['avg_knee_stability'] = x['shoeTrialResults']['raw_metrics']['Avg Knee Stability']['median']
            x['left_GC_vertical_oscillation'] = x['shoeTrialResults']['raw_metrics']['Left GC Vertical Oscillation']['median']
            x['right_GC_vertical_oscillation'] = x['shoeTrialResults']['raw_metrics']['Right GC Vertical Oscillation']['median']
            x['avg_GC_vertical_oscillation'] = x['shoeTrialResults']['raw_metrics']['Avg GC Vertical Oscillation']['median']
            x['left_norm_separation'] = x['shoeTrialResults']['raw_metrics']['Left Norm Separation']['median']
            x['right_norm_separation'] = x['shoeTrialResults']['raw_metrics']['Right Norm Separation']['median']
            x['avg_normal_separation'] = x['shoeTrialResults']['raw_metrics']['Avg Norm Separation']['median']
            x['left_knee_angle'] = x['shoeTrialResults']['raw_metrics']['Left Knee Angle']['median']
            x['right_knee_angle'] = x['shoeTrialResults']['raw_metrics']['Right Knee Angle']['median']
            x['avg_knee_angle'] = x['shoeTrialResults']['raw_metrics']['Avg Knee Angle']['median']
            x['left_knee_flexion'] = x['shoeTrialResults']['raw_metrics']['Left Knee Flexion']['median']
            x['right_knee_flexion'] = x['shoeTrialResults']['raw_metrics']['Right Knee Flexion']['median']
            x['avg_knee_flexion'] = x['shoeTrialResults']['raw_metrics']['Avg Knee Flexion']['median']
            x['vertical_stiffness'] = x['shoeTrialResults']['raw_metrics']['Vertical Stiffness']['median']
            x['duty_factor'] = x['shoeTrialResults']['raw_metrics']['Duty Factor']['median']
            x['right_dorsiflexion'] = x['shoeTrialResults']['raw_metrics']['Right Dorsiflexion']['median']
            x['left_orsiflexion'] = x['shoeTrialResults']['raw_metrics']['Left Dorsiflexion']['median']
            x['avg_dorsiflexion'] = x['shoeTrialResults']['raw_metrics']['Avg Dorsiflexion']['median']
            x['VOSL_magnitude'] = x['shoeTrialResults']['raw_metrics']['VOSL Magnitude']['median']

            if 'purchase_decision' not in x['shoeTrialResults']:
                x['purchase_decision'] = 2
            else:
                purchase_decision = x['shoeTrialResults']['purchase_decision']
                if purchase_decision is not None and isinstance(purchase_decision, dict) and 'decision' in purchase_decision:
                    x['purchase_decision'] = purchase_decision['decision']
                else:
                    x['purchase_decision'] = 2

            # x['no_sales_reason'] = x['shoeTrialResults']['purchase_decision']['no_sale_reason']
            
            del x['_id']
            del x['shoeTrialResults']['_id']
            del x['shoeTrialResults']['raw_metrics']
            del x['shoeTrialResults']['purchase_decision']
            yield messages_pb2.Customer(**x)