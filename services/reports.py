from datetime import datetime, timedelta
from bson.objectid import ObjectId
import grpc
from lib.query_utils import sort_cursor, save_html_to_file, convert_to_int, get_recommedation_value
import proto.messages_pb2 as messages_pb2
import proto.messages_pb2_grpc as messages_pb2_grpc
from decorators.required_role import check_role
from lib.timestamp import now, one_month_ago, one_week_ago, two_weeks_ago
from pymongo.database import Database
from lib.emai import send_email_with_html_attachment
import psutil
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


class ReportServicer(messages_pb2_grpc.ReportsServicer):
    def __init__(self, db: Database):
        self.db = db

    def get_no_sales_reasons(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': 2
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {'$group': {'_id': '$purchase_decision.no_sale_reason', 'count': {'$sum': 1}}})
        results = self.db.shoeTrialResults.aggregate(pipeline)
        reasons = {}
        for x in results:
            reasons[x['_id']] = x['count']
        return reasons

    def get_sales_counts(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                                'purchase_decision': {'$exists': True}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        pipeline.append({
            '$match': {'purchase_decision.decision': {'$in': [0, 1]}}
        })

        # Add "convertedDate" attribute to do date matching later

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {'$group': {'_id': {'date': {'$toDate': '$recording_date'}}, 'count': {'$sum': 1}}})

        results = self.db.shoeTrialResults.aggregate(pipeline)
        daily_performance = {}
        for x in results:
            date = x['_id']['date'].strftime('%d/%m/%Y')
            if date not in daily_performance:
                daily_performance[date] = x['count']
            else:
                daily_performance[date] += x['count']

        return daily_performance

    def get_scans_counts(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1, 2]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {'$group': {'_id': {'date': {'$toDate': '$recording_date'}}, 'count': {'$sum': 1}}})
        
        results = self.db.shoeTrialResults.aggregate(pipeline)
        daily_performance = {}
        results = list(results)
        for x in results:
            date = x['_id']['date'].strftime('%d/%m/%Y')
            if date not in daily_performance:
                daily_performance[date] = x['count']
            else:
                daily_performance[date] += x['count']
        return daily_performance

    def get_brand_sales(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {'$group': {'_id': '$shoe_brand', 'count': {'$sum': 1}}})

        brand_sales = self.db.shoeTrialResults.aggregate(pipeline)
        brands = {}
        for x in brand_sales:
            brands[x['_id']] = x['count']
        return brands

    def get_brand_sales_table(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1, 2]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {
                '$group': {
                    '_id': {
                        'brand': '$shoe_brand',
                        'decision': '$purchase_decision.decision'
                    },
                    'count': {'$sum': 1}
                }
            }
        )

        brand_sales = self.db.shoeTrialResults.aggregate(pipeline)

        brand_sales_summary = {}
        for x in brand_sales:
            brand = x['_id']['brand']
            decision = x['_id']['decision']
            count = x['count']
            if brand not in brand_sales_summary:
                brand_sales_summary[brand] = {'sale': 0, 'scan': 0} # Initialize counts for 'sale' and 'scan'
            if decision in [0, 1]:
                brand_sales_summary[brand]['sale'] += count # Sum up counts for 'sale' (decision 0 and 1)
            if decision in [0, 1, 2]:
                brand_sales_summary[brand]['scan'] += count # Sum up counts for 'scan' (decision 0, 1, and 2)

        result = []
        for brand, counts in brand_sales_summary.items():
            brand_obj = {'name': brand, 'sale': counts['sale'], 'scan': counts['scan']}
            result.append(messages_pb2.BrandSales(**brand_obj))

        return result

    def get_model_sales(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {'$group': {'_id': '$shoe_name', 'count': {'$sum': 1}}})

        brand_sales = self.db.shoeTrialResults.aggregate(pipeline)
        brands = {}
        for x in brand_sales:
            brands[x['_id']] = x['count']
        return brands

    def get_model_sales_table(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1, 2]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append(
            {
                '$group': {
                    '_id': {
                        'model': '$shoe_name',
                        'decision': '$purchase_decision.decision'
                    },
                    'count': {'$sum': 1}
                }
            }
        )

        model_sales = self.db.shoeTrialResults.aggregate(pipeline)

        model_sales = self.db.shoeTrialResults.aggregate(pipeline)

        model_sales_summary = {}
        for x in model_sales:
            model = x['_id']['model']
            decision = x['_id']['decision']
            count = x['count']
            if model not in model_sales_summary:
                model_sales_summary[model] = {'sale': 0, 'scan': 0} # Initialize counts for 'sale' and 'scan'
            if decision in [0, 1]:
                model_sales_summary[model]['sale'] += count # Sum up counts for 'sale' (decision 0 and 1)
            if decision in [0, 1, 2]:
                model_sales_summary[model]['scan'] += count # Sum up counts for 'scan' (decision 0, 1, and 2)

        result = []
        for model, counts in model_sales_summary.items():
            model_obj = {'name': model, 'sale': counts['sale'], 'scan': counts['scan']}
            result.append(messages_pb2.ModelSales(**model_obj))

        return result


    def get_top_technicians(self, start, end, company_id=None, branch_id=None, gender='0', season=None, brand=None):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision': {'$exists': True}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        pipeline.append({'$group': {
            '_id': {
                'technician': '$technician_id',
                'decision': '$purchase_decision.decision'
            },
            'count': {
                "$sum": 1
            }
        }})

        pipeline.append(
            {'$group': {
                '_id': "$_id.technician",
                'decisions': {
                    '$push': {
                        'decision': "$_id.decision",
                        'count': "$count"
                    }
                }
            }}
        )

        technician_decisions = self.db.shoeTrialResults.aggregate(pipeline)
        technicians = []
        for x in technician_decisions:
            user = self.db.users.find_one({'_id': ObjectId(x['_id'])})
            if user and user['branch_id']:
                company = self.db.companies.find_one({'branches.branch_id': user['branch_id']}, {'branches.$'})
                name = user['name']
                location = company['branches'][0]['name'] if user['branch_id'] else ''
            else:
                name = 'Deleted User'
                location = ''
            

            
            technicians.append(messages_pb2.TechnicianSales(**{
                'id': x['_id'],
                'name': name,
                'location': location,
                'purchase_decisions': {
                    x['decision']: x['count'] for x in x['decisions']
                }
            }))
        return technicians

    def get_size_group_sales(self, start, end, company_id=None, branch_id=None, technician_id=None, season=None, brand=None):
        pipeline = []

        pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        pipeline.append(
            {'$group': {'_id': {'shoe_size': '$shoe_size', 'gender': '$customer_info.gender'}, 'count': {'$sum': 1}}})

        size_sales = self.db.shoeTrialResults.aggregate(pipeline)
        size = []

        for x in size_sales:
            gender_list = x['_id'].get('gender', [])
            gender = int(gender_list[0]) if gender_list else None

            if gender != 0:
                size.append(messages_pb2.SizeGenderSales(**{
                    'size': str(x['_id']['shoe_size']),
                    'gender': gender,
                    'count': x['count']
                }))

        return size

    def get_table_record(self, start, end, company_id=None, branch_id=None, technician_id=None, gender='0', season=None, brand=None):
        pipeline = []

        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        if season:
            pipeline.append({
                '$match': {'shoe_season': season}
            })

        if gender == '1':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 1
                }
            })

        if gender == '2':
            pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

            pipeline.append({
                '$match': {
                'customer_info.gender': 2
                }
            })

        tableRecords = self.db.shoeTrialResults.aggregate(pipeline)
        tableResult = []

        for x in tableRecords:
            technicianInfo = self.db.users.find_one({'_id': ObjectId(x['technician_id'])})
            companyInfo = self.db.companies.find_one({'_id': ObjectId(x['company_id'])})
            customerInfo = self.db.customers.find_one({'_id': ObjectId(x['customer_id'])})

            name = ''
            season = ''
            shoe_model = ''
            gender = ''

            if technicianInfo:
                name = technicianInfo['name']
            else:
                name = ''

            if x.get('shoe_season') == None:
                season = ''
            else:
                season = x['shoe_season']

            if x.get('shoe_model') == None:
                shoe_model = ''
            else:
                shoe_model = x['shoe_model']

            if customerInfo: 
                gender = str(customerInfo['gender'])
            else:
                gender = ''

            matching_entry = next((entry['name'] for entry in companyInfo['branches'] if entry['branch_id'] == x['branch_id']), None)

            tableResult.append(messages_pb2.DashboardTableRecord(**{
                'id': str(x['_id']),
                'gender': gender,
                'season': season,
                'brand': x['shoe_brand'],
                'model': shoe_model,
                'size': x['shoe_size'],
                'purchase': str(x['purchase_decision']['decision']),
                'reason': str(x['purchase_decision']['no_sale_reason']),
                'tech': name,
                'store': matching_entry,
                'recording_date': str(x['recording_date'])
            }))

        return tableResult

    def get_aged_sales(self, start, end, company_id=None, branch_id=None, technician_id=None, brand=None):
        current_year = datetime.now().year

        start_date_ss = datetime(current_year, 1, 1).date()
        end_date_ss = datetime(current_year, 7, 1).date()

        end_date_aw = datetime(current_year, 7, 1).date()

        # Get the current date
        current_date = datetime.now().date()

        # Compare the current date with the date ranges
        if start_date_ss <= current_date < end_date_ss:
            result = f"SS{current_year % 100}"  # Extract last two digits of the year
        elif current_date >= end_date_aw:
            result = f"AW{current_year % 100}"
        else:
            result = "No matching condition"

        pipeline = []

        pipeline.append({
                '$lookup': {
                    'from': 'customers',
                    'localField': 'customer_id',
                    'foreignField': 'customer_id',
                    'as': 'customer_info'
                }
            })

        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                },
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )
        if company_id:
            pipeline.append({
                '$match': {'company_id': company_id}
            })

        if branch_id:
            pipeline.append({
                '$match': {'branch_id': branch_id}
            })

        if technician_id:
            pipeline.append({
                '$match': {'technician_id': technician_id}
            })

        if brand:
            pipeline.append({
                '$match': {'shoe_brand': brand}
            })

        pipeline.append({
            '$match': {'shoe_season': { '$ne': result }}
        })

        pipeline.append({
            '$group': {
                '_id': 'null',
                'cnt': { '$sum': 1 }
            }
        })

        aged_sales = self.db.shoeTrialResults.aggregate(pipeline)

        aged_count = 0

        for x in aged_sales:
            aged_count = x['cnt']

        return aged_count

    @check_role([2, 3, 4, 5, 6])
    def GetDashboardReport(self, request: messages_pb2.ReportQuery, context) -> messages_pb2.DashboardReport:
        # Always filter by at least a company and a date frame
        if context.user['role'] not in [5, 6]:
            if not request.company_id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              'company_id is required')
                return

            # Ensure that the company specified is allowed for this user
            if not request.company_id == str(context.user['company_id']):
                context.abort(grpc.StatusCode.PERMISSION_DENIED,
                              'you cannot view reports for other companies')
                return

        start = request.start_millis
        end = request.end_millis
        
        daily_scans = self.get_scans_counts(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        daily_sales = self.get_sales_counts(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        no_sale_reasons = self.get_no_sales_reasons(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        technician_sales = self.get_top_technicians(
            start, end, request.company_id, request.branch_id, request.gender, request.season, request.brand)
        brand_sales = self.get_brand_sales(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        brand_sales_table = self.get_brand_sales_table(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        model_sales = self.get_model_sales(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        model_sales_table = self.get_model_sales_table(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        table_records = self.get_table_record(
            start, end, request.company_id, request.branch_id, request.technician_id, request.gender, request.season, request.brand)
        size_gender_sales = self.get_size_group_sales(
            start, end, request.company_id, request.branch_id, request.technician_id, request.season, request.brand
        )
        aged_sales_count = self.get_aged_sales(start, end, request.company_id, request.branch_id, request.technician_id, request.brand)
        report = messages_pb2.DashboardReport(
            daily_sales=daily_sales, daily_scans=daily_scans, no_sale_reasons=no_sale_reasons, brand_sales=brand_sales, model_sales=model_sales, aged_sales_count=aged_sales_count)
        report.technician_sales.extend(technician_sales)
        report.dashboard_table_record.extend(table_records)
        report.size_gender_sales.extend(size_gender_sales)
        report.brand_sales_table.extend(brand_sales_table)
        report.model_sales_table.extend(model_sales_table)
        return report

    @check_role([2, 3, 4, 5, 6])
    def GetNoSaleRecords(self, request: messages_pb2.NoSaleQuery, context):
        # Always filter by at least a company and a date frame
        if not request.query.company_id and context.user['role'] not in [5, 6]:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'company_id is required')
            return

        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': request.query.start_millis,
                                '$lte': request.query.end_millis
                                },
                    'purchase_decision.no_sale_reason': request.reason,
                },
            }
        )
        if request.query.company_id:
            pipeline.append({
                '$match': {'company_id': request.query.company_id}
            })

        if request.query.technician_id:
            pipeline.append({
                '$match': {'technician_id': request.query.technician_id}
            })

        if request.query.branch_id:
            pipeline.append({
                '$match': {'branch_id': request.query.branch_id}
            })

        skip = request.query.skip
        pipeline.append({
            '$skip': int(skip)
        })

        limit = request.query.limit
        if limit <= 50 and limit > 0:
            pipeline.append({
                '$limit': int(limit if limit else 10)
            })

        shoeTrialResults = self.db.shoeTrialResults.aggregate(pipeline)
        for x in shoeTrialResults:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.company_id = str(x['company_id'])
            msg.branch_id = str(x['branch_id'])
            msg.technician_id = str(x['technician_id'])
            yield msg

    def GetBrandModelSaleCounts(self, request, context):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': request.query.start_millis,
                                '$lte': request.query.end_millis
                                },
                    'shoe_brand': request.brand,
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )

        if request.query.technician_id:
            pipeline.append({
                '$match': {'technician_id': request.query.technician_id}
            })

        if request.query.branch_id:
            pipeline.append({
                '$match': {'branch_id': request.query.branch_id}
            })

        pipeline.append({'$group': {'_id': '$shoe_name', 'count': {'$sum': 1}}})
        brand_sale_counts = self.db.shoeTrialResults.aggregate(pipeline)
        sale_counts = {x['_id']: x['count'] for x in brand_sale_counts}
        return messages_pb2.BrandModelSaleCounts(sale_counts=sale_counts)
        

    @check_role([2, 3, 4, 5, 6])
    def GetBrandSaleRecords(self, request, context):
        pipeline = []
        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': request.query.start_millis,
                                '$lte': request.query.end_millis
                                },
                    'shoe_brand': request.brand,
                    'purchase_decision.decision': {'$in': [0, 1]}
                },
            }
        )

        if request.query.technician_id:
            pipeline.append({
                '$match': {'technician_id': request.query.technician_id}
            })

        if request.query.branch_id:
            pipeline.append({
                '$match': {'branch_id': request.query.branch_id}
            })

        skip = request.query.skip
        pipeline.append({
            '$skip': int(skip)
        })

        limit = request.query.limit
        if limit <= 50 and limit > 0:
            pipeline.append({
                '$limit': int(limit if limit else 10)
            })

        shoeTrialResults = self.db.shoeTrialResults.aggregate(pipeline)
        for x in shoeTrialResults:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.company_id = str(x['company_id'])
            msg.branch_id = str(x['branch_id'])
            msg.technician_id = str(x['technician_id'])
            yield msg

    @check_role([2, 3, 4, 5, 6])
    def GetTechSaleRecords(self, request: messages_pb2.ReportQuery, context):
        pipeline = []

        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': request.start_millis,
                                '$lte': request.end_millis
                                },
                    'technician_id': request.technician_id,
                    'purchase_decision': {'$exists': True}
                },
            }
        )

        skip = request.skip
        pipeline.append({
            '$skip': int(skip)
        })

        limit = request.limit
        if limit <= 50 and limit > 0:
            pipeline.append({
                '$limit': int(limit if limit else 10)
            })

        shoeTrialResults = self.db.shoeTrialResults.aggregate(pipeline)
        for x in shoeTrialResults:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.company_id = str(x['company_id'])
            msg.branch_id = str(x['branch_id'])
            msg.technician_id = str(x['technician_id'])
            yield msg

    @check_role([2, 3, 4, 5, 6])
    def GetDailySaleScanRecords(self, request: messages_pb2.SaleScanRecordsQuery, context):
        pipeline = []

        if request.date:
            specified_day = datetime.strptime(request.date, '%d/%m/%Y')
            start = datetime(specified_day.year,
                            specified_day.month, specified_day.day)
            end = int((start + timedelta(days=1)).timestamp()) * 1000
            start = int(start.timestamp()) * 1000
        else:
            start = request.query.start_millis
            end = request.query.end_millis
            

        pipeline.append(
            {
                '$match': {
                    'recording_date': {'$gte': start,
                                '$lte': end
                                }
                },
            }
        )

        if request.type == 'sales':
            pipeline.append({
                '$match' :{'purchase_decision.decision': {'$in': [0,1]}}
            })

        if request.query.company_id:
            pipeline.append({
                '$match': {'company_id': request.query.company_id}
            })

        if request.query.branch_id:
            pipeline.append({
                '$match': {'branch_id': request.query.branch_id}
            })

        if request.query.technician_id:
            pipeline.append({
                '$match': {'technician_id': request.query.technician_id}
            })

        pipeline.append({ '$sort': { 'recording_date': 1} })

        

        skip = request.query.skip
        pipeline.append({
            '$skip': int(skip)
        })

        limit = request.query.limit
        if limit <= 50 and limit > 0:
            pipeline.append({
                '$limit': int(limit)
            })

        results = self.db.shoeTrialResults.aggregate(pipeline)
        for x in results:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.company_id = str(x['company_id'])
            msg.branch_id = str(x['branch_id'])
            msg.technician_id = str(x['technician_id'])
            msg.created = x['created']
            yield msg

    @check_role([2, 3, 4, 5, 6])
    def GetSeasons(self, request: messages_pb2.ReportQuery, context) -> messages_pb2.DashboardReport:
        pipeline = []

        pipeline.append(
            {'$group': {'_id': '$shoe_season', 'count': {'$sum': 1}}})

        results = self.db.shoeTrialResults.aggregate(pipeline)
        for x in results:
            msg = messages_pb2.SeasonSelector()
            if str(x['_id']) != '':
                msg.shoe_season = str(x['_id'])
                yield msg

    @check_role([2, 3, 4, 5, 6])
    def GetBrandsSelector(self, request: messages_pb2.ReportQuery, context) -> messages_pb2.DashboardReport:
        pipeline = []

        pipeline.append(
            {'$group': {'_id': '$shoe_brand', 'count': {'$sum': 1}}})

        results = self.db.shoeTrialResults.aggregate(pipeline)
        for x in results:
            msg = messages_pb2.ShoeTrialResult()
            if str(x['_id']) != '':
                msg.shoe_brand = str(x['_id'])
                yield msg

    @check_role([4, 5, 6])
    def GenerateHtml(self, request: messages_pb2.ReportQuery, context) -> messages_pb2.DashboardReport:
        report_str = ''
        if request.branch_id is not None:
            report_str = request.branch_id
        else:
            report_str = "66a385671787b6f379a2b4ad"
        print(report_str)
        report_id = ObjectId(report_str)
        result = self.db.shoeTrialResults.find_one({"_id": report_id})
        customer = self.db.customers.find_one({"_id": ObjectId(result['customer_id'])})
        user = self.db.users.find_one({"_id": ObjectId(result['technician_id'])})
        branch_company = self.db.companies.find_one({"_id": ObjectId(user['company_id'])})
        companies = self.db.companies.find_one({"_id": ObjectId(result['company_id'])})

        with open(f"/home/AvaAdmin/data/temp_email/template.html", 'r', encoding='utf-8') as file:
        # with open(f"/home/neymar/AvaAdmin/data/temp_email/template.html", 'r', encoding='utf-8') as file:              
          html = file.read()

        ground_str1 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your average GCT is <span style="font-weight: bold">%raw_value%</span>ms, which is <span style="font-weight: bold;">%minus_score%m</span>s or <span style="font-weight: bold;">%percent%</span>% too long. <br><br>
            Ground contact time, or GCT, is the time each foot spends on the ground when you run. Your GCT is not just a metric; it's a key to unlocking your performance potential and preventing injuries. It's when your foot can brake, stabilise, and propel you. A shorter GCT means you’re running more efficiently, using less energy for braking and more for moving forward. This understanding can motivate you to optimise your form and energy use, as even a tiny imbalance in your GCT can make running significantly harder. Looking at GCT between left and right, how even are your feet on the ground? A slight imbalance can make running a lot harder. Elite runners tweak their form to keep energy use low, which is called self-optimisation. 
        """

        ground_str2 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your average GCT is <span style="font-weight: bold">%raw_value%</span>ms, which is <span style="font-weight: bold;">%minus_score%m</span>s or <span style="font-weight: bold;">%percent%</span>% better than Elite  <br><br>
            Ground contact time, or GCT, is the time each foot spends on the ground when you run. Your GCT is not just a metric, it's a key to unlocking your performance potential and preventing injuries. It's when your foot can brake, stabilise, and propel you. A shorter GCT means you’re running more efficiently, using less energy for braking and more for moving forward. This understanding can motivate you to optimise your form and energy use, as even a tiny imbalance in your GCT can make running significantly harder. Looking at GCT between left and right, how even are your feet on the ground? A slight imbalance can make running a lot harder. Elite runners tweak their form to keep energy use low, which is called self-optimisation. Runright 3D measures the effect of different shoe models on how long you keep each of your feet on the ground.
        """

        ground_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your average GCT is <span style="font-weight: bold">%raw_value%</span>ms, the same as an Elite runner. <br><br>
            Ground contact time, or GCT, is the time each foot spends on the ground when you run. Your GCT is not just a metric, it's a key to unlocking your performance potential and preventing injuries. It's when your foot can brake, stabilise, and propel you. So, a shorter GCT means you’re running more efficiently, using less energy for braking and more for moving forward. This understanding can motivate you to optimise your form and energy use. Looking at GCT between left and right, how even are your feet on the ground? A slight imbalance can make running a lot harder. Elite runners tweak their form to keep energy use low, which is called self-optimisation. Runright 3D measures the effect of different shoe models on how long you keep each of your feet on the ground.
        """

        vertical_str1 = """
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Vertical Oscillation is recorded at <span style="font-weight: bold">%raw_value%</span>mm, <span style="font-weight: bold;">%minus_score%m</span>m, or <span style="font-weight: bold;">%percent%</span>% above our Elite Score. <br><br>
            A high vertical oscillation wastes energy and increases landing loads. If you decide to lower your vertical oscillation, remember that changing your running form may temporarily increase your energy consumption. RUNRIGHT 3D can help you find the shoes that bring you closer to your sweet spot, reducing tibial shock and metabolic demand, improving efficiency, and decreasing strain.
        """

        vertical_str2 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Vertical Oscillation is recorded at <span style="font-weight: bold">%raw_value%</span>mm, <span style="font-weight: bold;">%minus_score%m</span>m, or <span style="font-weight: bold;">%percent%</span>% below our Elite Score. <br><br>
            A vertical oscillation that is too low often increases ground contact time and impairs your running form. If you want to improve your vertical oscillation, remember that changing your running form may temporarily increase your energy consumption. RUNRIGHT 3D can help you find the shoes that bring you closer to your sweet spot, reducing tibial shock and metabolic demand, improving efficiency, and decreasing strain.
        """

        vertical_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Well done, your Vertical Oscillation is spot on, measuring <span style="font-weight: bold">%raw_value%</span>mm; that is the Elite Score benchmark! <br><br>
            Continue to monitor your vertical oscillation. Any reduction may increase ground contact time and impair your running form. Any increase wastes energy and increases landing forces. RUNRIGHT 3D can help you find the shoes that bring you closer to your sweet spot, reducing tibial shock and metabolic demand, improving efficiency, and decreasing strain.
        """

        cadence_str1 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Cadence is recorded at <span style="font-weight: bold">%raw_value%</span>spm, <span style="font-weight: bold;">%minus_score%sp</span>m or <span style="font-weight: bold;">%percent%</span>% above your target of <span style="font-weight: bold;">%elite_score%</span>spm <br>
            Your cadence is above your target score, increasing injury risks and raising your heart rate. Ultimately, you are turning your legs over too fast to maintain speed. RUNRIGHT 3D suggests a target cadence of <span style="font-weight: bold;">%elite_score%</span>spm based on your height and running speed, but cadence is not one-size-fits-all. Therefore, finding what is best for you is essential. Your ‘happy place’ is the right cadence for your current strength and fitness. It’s like being in the right gear on a bike, not pushing too hard or spinning too fast.
        """

        cadence_str2 = """
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Cadence is recorded at <span style="font-weight: bold">%raw_value%</span>spm, <span style="font-weight: bold;">%minus_score%sp</span>m or <span style="font-weight: bold;">%percent%</span>% below your target of <span style="font-weight: bold;">%elite_score%</span>spm <br><br>
            Your running cadence is below your target. Essentially, you're not turning your legs fast enough to maintain speed, so you may be overstriding to compensate. RUNRIGHT 3D suggests a target cadence of <span style="font-weight: bold;">%elite_score%</span>spm based on your height and running speed, but it's important to note that cadence is not one-size-fits-all. Therefore, it's essential to find what works best for you. Your 'happy place' is the right cadence for your current strength and fitness level. It's like being in the right gear on a bike – not pushing too hard or spinning too fast.
        """

        cadence_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Well done, your Cadence equals the Elite target! <br><br>
            Your cadence equals your target score of <span style="font-weight: bold;">%elite_score%</span>spm, which is ideal for your current height and running speed. But please note that cadence is not a one-size-fits-all. Your ‘happy place’ is the right cadence for your current strength and fitness. It’s like being in the right gear on a bike, not pushing too hard or spinning too fast.
        """

        stiffness_str1 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Vertical Stiffness was recorded at <span style="font-weight: bold">%raw_value%</span>KN/m, <span style="font-weight: bold;">%minus_score%k</span>N/m or <span style="font-weight: bold;">%percent%</span>% above your target score of <span style="font-weight: bold;">%elite_score%</span>KN/m. <br><br>
            Vertical stiffness refers to the ability of your legs to function as 'high-tech' springs. When your foot makes contact with the ground, a ground reaction force pushes back (according to Newton's Law). With stiffer leg-springs, there is less drop in your CoM and a quicker return, conserving valuable energy. The goal is to fine-tune your body's springs to reduce effort and oxygen consumption. When done right, running is effortless. Runright 3D measures and compares the degree of CoM drop in various types of running shoes.
        """
        
        stiffness_str2 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Vertical Stiffness was recorded at <span style="font-weight: bold">%raw_value%</span>KN/m, <span style="font-weight: bold;">%minus_score%k</span>N/m or <span style="font-weight: bold;">%percent%</span>% below your target score of <span style="font-weight: bold;">%elite_score%</span>KN/m. <br><br>
            Vertical stiffness refers to the ability of your legs to function as 'high-tech' springs. When your foot makes contact with the ground, a ground reaction force pushes back (according to Newton's Law). With stiffer leg-springs, there is less drop in your CoM and a quicker return, conserving valuable energy. The goal is to fine-tune your body's springs to reduce effort and oxygen consumption. When done right, running is effortless. Runright 3D measures and compares the degree of CoM drop in various types of running shoes.
        """

        stiffness_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Well done! Your Vertical Stiffness is spot on at <span style="font-weight: bold">%raw_value%</span>KN/m, which matches the elite target. <br><br>
            Continue to monitor your Vertical Stiffness. When done right, running is effortless. Runright 3D measures and compares the degree of CoM drop in various types of running. Your score indicates that you have found your ‘happy place’ for your current strength and fitness; keep it. RUNRIGHT 3-D aims to find a shoe that helps you reduce Vertical Stiffness. 
        """

        overstride_str1 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Overstriding is recorded at <span style="font-weight: bold">%raw_value%</span>mm, <span style="font-weight: bold;">%minus_score%m</span>m or <span style="font-weight: bold;">%percent%</span>% above your target score of <span style="font-weight: bold;">%elite_score%</span>mm. <br><br>
            Your foot lands too far ahead of your body's centre of mass (COM), which can cause a higher braking force with each step. Regardless of the foot’s point of contact with the ground—heel, midfoot, or forefoot—the resulting braking force can increase stress on the joints and soft tissues, potentially leading to injury and reducing running economy. Elite runners (dependent on speed) tend to land slightly in front but not excessively. Runright 3D calculates a recommended overstride based on height, speed, and age.
        """ 

        overstride_str2 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Overstriding is recorded at <span style="font-weight: bold">%raw_value%</span>mm, <span style="font-weight: bold;">%minus_score%m</span>m or <span style="font-weight: bold;">%percent%</span>% below your target score of <span style="font-weight: bold;">%elite_score%</span>mm. <br><br>
            Your foot lands a little too close to your body's centre of mass (COM), which reduces your forward momentum, making it harder to use force during the push-off phase of your gait. This is because you cannot store energy during the braking phase. Landing your foot too far under your body is inefficient. Elite runners (dependent on speed) tend to land slightly in front but not excessively. Runright 3D calculates a recommended overstride based on height, speed, and age.
        """ 

        overstride_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Well done! Your Overstride is spot on at <span style="font-weight: bold">%raw_value%</span>mm, which matches the elite target score.ore.
            Continue to monitor your Overstride. Too far forward, and you increase loading forces on your joints, increasing the risk of injury and reducing your running economy. Too far beneath your body is just inefficient. Your score indicates that you have found your ‘happy place’ for your current strength and fitness; keep it.
        """

        braking_str1 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Braking Power was recorded at <span style="font-weight: bold">%raw_value%</span>W/kg, <span style="font-weight: bold;">%minus_score%</span>W/kg or <span style="font-weight: bold;">%percent%</span>% above your target score of <span style="font-weight: bold;">%elite_score%</span>W/kg. <br><br>
            Your braking force is too strong, which means you are using more negative energy and storing less elastic energy. This affects your ability to propel/accelerate, requiring more muscle-generated positive energy. In simpler terms, excessive braking power puts more strain on your muscles and joints, leading to quicker fatigue and a higher risk of injury. The goal of RUNRIGHT 3-D is to find a shoe that can help reduce braking power.
        """ 

        braking_str2 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Your Braking Power was recorded at <span style="font-weight: bold">%raw_value%</span>W/kg, <span style="font-weight: bold;">%minus_score%</span>W/kg or <span style="font-weight: bold;">%percent%</span>% below your target score of <span style="font-weight: bold;">%elite_score%</span>W/kg. <br><br>
            Braking Power refers to the amount of energy your legs require from initial contact to midstance, and it stores elastic energy. Lower braking power is better. The good news is your braking force is low and better than the elite target. In simple terms, lower braking power reduces joint muscle exertion and flexion, increasing your efficiency while reducing the risk of injury. RUNRIGHT 3-D aims to find a shoe that helps you reduce braking power.
        """ 

        braking_str3 = """ 
            <p style="margin:0px; font-size: 14px; font-weight: bold">Your score <span style="color: orange">%score%</span> &nbsp;&nbsp; Recommendation <span style="color: orange">%recommendation_value%</span></p>
            Well done! Your Braking Power is spot on at <span style="font-weight: bold">%raw_value%</span>mm, which matches the elite target score.ore.
            Continue to monitor your braking power. Using too much braking power can result in wasted energy, increased joint exertion, and a higher risk of injury. Your score shows that you have found the optimal level for your current strength and fitness, so maintain it. RUNRIGHT 3-D seeks to design a shoe that can help you minimize braking power.
        """
        
        # overall values
        shoe_performance = result['macro_metric_results']['Performance']['score']
        shoe_protection = result['macro_metric_results']['Protection']['score']
        shoe_efficiency = result['macro_metric_results']['Efficiency']['score']
        shoe_energy = result['macro_metric_results']['Energy']['score']
        overall = (shoe_efficiency + shoe_performance + shoe_energy + shoe_protection) / 4

        html = html.replace('%overall_value%', convert_to_int(overall))
        html = html.replace('%performance_value%', convert_to_int(shoe_performance))
        html = html.replace('%protection_value%', convert_to_int(shoe_protection))
        html = html.replace('%efficiency_value%', convert_to_int(shoe_efficiency))
        html = html.replace('%energy_value%', convert_to_int(shoe_energy))

        # Performance Ground Contact values
        performance_ground_contact_left_raw = result['macro_metric_results']['Performance']['component_scores']['Left Ground Contact']['micro_metric_score']['raw_value'] 
        performance_ground_contact_right_raw = result['macro_metric_results']['Performance']['component_scores']['Right Ground Contact']['micro_metric_score']['raw_value'] 
        performance_ground_contact_left_elite = result['macro_metric_results']['Performance']['component_scores']['Left Ground Contact']['micro_metric_score']['elite_score'] 
        performance_ground_contact_right_elite = result['macro_metric_results']['Performance']['component_scores']['Right Ground Contact']['micro_metric_score']['elite_score']
        performance_ground_contact_left_score = result['macro_metric_results']['Performance']['component_scores']['Left Ground Contact']['micro_metric_score']['score'] 
        performance_ground_contact_right_score = result['macro_metric_results']['Performance']['component_scores']['Right Ground Contact']['micro_metric_score']['score']

        performance_ground_contact_left_weight =  performance_ground_contact_left_elite / performance_ground_contact_left_raw * 100
        performance_ground_contact_right_weight = performance_ground_contact_right_elite / performance_ground_contact_right_raw * 100

        performance_ground_contact_elite = (performance_ground_contact_left_elite + performance_ground_contact_right_elite) / 2
        performance_ground_contact_score = (performance_ground_contact_left_score + performance_ground_contact_right_score) / 2
        performance_ground_contact_left_graph_height = 0.25 * performance_ground_contact_left_raw
        performance_ground_contact_right_graph_height = 0.25 * performance_ground_contact_right_raw
        performance_ground_contact_elite_graph_height = 0.25 * performance_ground_contact_elite
        
        performance_ground_contact_left_margin = 160 - 28 - performance_ground_contact_left_graph_height
        performance_ground_contact_right_margin = 160 - 28 - performance_ground_contact_right_graph_height
        performance_ground_contact_elite_margin = 160 - 28 - performance_ground_contact_elite_graph_height
        performance_ground_contact_value = convert_to_int((performance_ground_contact_left_weight + performance_ground_contact_right_weight) / 2)

        html = html.replace('%performance_ground_contact_left_graph_height%', convert_to_int(performance_ground_contact_left_graph_height))
        html = html.replace('%performance_ground_contact_right_graph_height%', convert_to_int(performance_ground_contact_right_graph_height))
        html = html.replace('%performance_ground_contact_left_margin%', convert_to_int(performance_ground_contact_left_margin))
        html = html.replace('%performance_ground_contact_right_margin%', convert_to_int(performance_ground_contact_right_margin))
        html = html.replace('%performance_ground_contact_value%', convert_to_int(performance_ground_contact_value))
        html = html.replace('%performance_ground_contact_left_raw%', convert_to_int(performance_ground_contact_left_raw))
        html = html.replace('%performance_ground_contact_right_raw%', convert_to_int(performance_ground_contact_right_raw))
        html = html.replace('%performance_ground_contact_elite%', convert_to_int(performance_ground_contact_elite))
        html = html.replace('%performance_ground_contact_elite_graph_height%', convert_to_int(performance_ground_contact_elite_graph_height))
        html = html.replace('%performance_ground_contact_elite_margin%', convert_to_int(performance_ground_contact_elite_margin))
        html = html.replace('%performance_ground_score%', convert_to_int(performance_ground_contact_score))

        if int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2) > int(performance_ground_contact_elite):
            description = ground_str1
            description = description.replace('%score%', str(int(performance_ground_contact_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_ground_contact_score))
            description = description.replace('%raw_value%', convert_to_int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int((int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2)) - int(performance_ground_contact_elite)))
            description = description.replace('%percent%', str(int((((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2) - performance_ground_contact_elite) / ((performance_ground_contact_elite) / 100))))
            html = html.replace('%performance_ground_description%', description)
        elif int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2) < int(performance_ground_contact_elite):
            description = ground_str2
            description = description.replace('%score%', str(int(performance_ground_contact_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_ground_contact_score))
            description = description.replace('%raw_value%', convert_to_int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int((int((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2))))
            description = description.replace('%percent%', str(int((performance_ground_contact_elite - ((performance_ground_contact_left_raw + performance_ground_contact_right_raw) / 2)) / ((performance_ground_contact_elite) / 100))))
            html = html.replace('%performance_ground_description%', description)
        else:
            description = ground_str3
            description = description.replace('%score%', str(int(performance_ground_contact_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_ground_contact_score))
            description = description.replace('%raw_value%', convert_to_int(performance_ground_contact_elite))
            html = html.replace('%performance_ground_description%', description)

        # Performance Vertical Oscillation values
        performance_vertical_raw = result['macro_metric_results']['Performance']['component_scores']['Vertical Oscillation']['micro_metric_score']['raw_value']
        performance_vertical_elite = result['macro_metric_results']['Performance']['component_scores']['Vertical Oscillation']['micro_metric_score']['elite_score']
        performance_vertical_score = result['macro_metric_results']['Performance']['component_scores']['Vertical Oscillation']['micro_metric_score']['score']
        performance_vertical_weight = performance_vertical_elite / performance_vertical_raw * 100

        performance_vertical_elite_graph_height = 0.25 * performance_vertical_elite
        performance_vertical_graph_height = 0.25 * performance_vertical_raw
        performance_vertical_margin = 160 - 28 - performance_vertical_graph_height
        performance_vertical_elite_margin = 160 - 28 - performance_vertical_elite_graph_height

        html = html.replace('%performance_vertical_weight%', convert_to_int(performance_vertical_weight))
        html = html.replace('%performance_vertical_raw%', convert_to_int(performance_vertical_raw))
        html = html.replace('%performance_vertical_graph_height%', convert_to_int(performance_vertical_graph_height))
        html = html.replace('%performance_vertical_margin%', convert_to_int(performance_vertical_margin))
        html = html.replace('%performance_vertical_elite%', convert_to_int(performance_vertical_elite))
        html = html.replace('%performance_vertical_elite_graph_height%', convert_to_int(performance_vertical_elite_graph_height))
        html = html.replace('%performance_vertical_elite_margin%', convert_to_int(performance_vertical_elite_margin))
        html = html.replace('%performance_vertical_score%', convert_to_int(performance_vertical_score))
        
        if int(performance_vertical_raw) > int(performance_vertical_elite):
            description = vertical_str1
            description = description.replace('%score%', str(int(performance_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(performance_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(performance_vertical_raw) - int(performance_vertical_elite)))
            description = description.replace('%percent%', str(int((performance_vertical_raw - performance_vertical_elite) / ((performance_vertical_elite) / 100))))
            html = html.replace('%performance_vertical_description%', description)
        elif int(performance_vertical_raw) < int(performance_vertical_elite):
            description = vertical_str2
            description = description.replace('%score%', str(int(performance_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(performance_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(performance_vertical_elite) - int(performance_vertical_raw)))
            description = description.replace('%percent%', str(int((performance_vertical_elite - performance_vertical_raw) / ((performance_vertical_elite) / 100))))
            html = html.replace('%performance_vertical_description%', description)
        else:
            description = vertical_str3
            description = description.replace('%score%', str(int(performance_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(performance_vertical_raw))
            html = html.replace('%performance_vertical_description%', description)

        # Performance Overstride values
        performance_overstride_left_raw = result['macro_metric_results']['Performance']['component_scores']['Left Overstride']['micro_metric_score']['raw_value'] 
        performance_overstride_right_raw = result['macro_metric_results']['Performance']['component_scores']['Right Overstride']['micro_metric_score']['raw_value'] 
        performance_overstride_left_elite = result['macro_metric_results']['Performance']['component_scores']['Left Overstride']['micro_metric_score']['elite_score'] 
        performance_overstride_right_elite = result['macro_metric_results']['Performance']['component_scores']['Right Overstride']['micro_metric_score']['elite_score'] 
        performance_overstride_left_score = result['macro_metric_results']['Performance']['component_scores']['Left Overstride']['micro_metric_score']['score'] 
        performance_overstride_right_score = result['macro_metric_results']['Performance']['component_scores']['Right Overstride']['micro_metric_score']['score'] 
        performance_overstride_left_weight = performance_overstride_left_elite / performance_overstride_left_raw * 100
        performance_overstride_right_weight = performance_overstride_right_elite / performance_overstride_right_raw * 100

        performance_overstride_elite = (performance_overstride_left_elite + performance_overstride_right_elite) / 2
        performance_overstride_score = (performance_overstride_left_score + performance_overstride_right_score) / 2
        performance_overstride_left_graph_height = 0.25 * performance_overstride_left_raw
        performance_overstride_right_graph_height = 0.25 * performance_overstride_right_raw
        performance_overstride_elite_graph_height = 0.25 * performance_overstride_elite
        performance_overstride_left_margin = 160 - 28 - performance_overstride_left_graph_height
        performance_overstride_right_margin = 160 - 28 - performance_overstride_right_graph_height
        performance_overstride_elite_margin = 160 - 28 - performance_overstride_elite_graph_height

        performance_overstride_value = convert_to_int((performance_overstride_left_weight + performance_overstride_right_weight) / 2)

        html = html.replace('%performance_overstride_left_raw%', convert_to_int(performance_overstride_left_raw))
        html = html.replace('%performance_overstride_right_raw%', convert_to_int(performance_overstride_right_raw))
        html = html.replace('%performance_overstride_left_graph_height%', convert_to_int(performance_overstride_left_graph_height))
        html = html.replace('%performance_overstride_right_graph_height%', convert_to_int(performance_overstride_right_graph_height))
        html = html.replace('%performance_overstride_left_margin%', convert_to_int(performance_overstride_left_margin))
        html = html.replace('%performance_overstride_right_margin%', convert_to_int(performance_overstride_right_margin))
        html = html.replace('%performance_overstride_value%', convert_to_int(performance_overstride_value))
        html = html.replace('%performance_overstride_elite%', convert_to_int(performance_overstride_elite))
        html = html.replace('%performance_overstride_elite_graph_height%', convert_to_int(performance_overstride_elite_graph_height))
        html = html.replace('%performance_overstride_elite_margin%', convert_to_int(performance_overstride_elite_margin))
        html = html.replace('%performance_overstride_score%', convert_to_int(performance_overstride_score))

        if int((performance_overstride_left_raw + performance_overstride_right_raw) / 2) > int(performance_overstride_elite):
            description = overstride_str1
            description = description.replace('%score%', str(int(performance_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((performance_overstride_left_raw + performance_overstride_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int(int((performance_overstride_left_raw + performance_overstride_right_raw) / 2) - int(performance_overstride_elite)))
            description = description.replace('%percent%', str(int((((performance_overstride_left_raw + performance_overstride_right_raw) / 2) - performance_overstride_elite) / ((performance_overstride_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(performance_overstride_elite))
            html = html.replace('%performance_overstride_description%', description)
        elif int((performance_overstride_left_raw + performance_overstride_right_raw) / 2) < int(performance_overstride_elite):
            description = overstride_str2
            description = description.replace('%score%', str(int(performance_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((performance_overstride_left_raw + performance_overstride_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int(int(performance_overstride_elite) - int((performance_overstride_left_raw + performance_overstride_right_raw) / 2)))
            description = description.replace('%percent%', str(int((performance_overstride_elite - ((performance_overstride_left_raw + performance_overstride_right_raw) / 2)) / ((performance_overstride_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(performance_overstride_elite))
            html = html.replace('%performance_overstride_description%', description)
        else:
            description = overstride_str3
            description = description.replace('%score%', str(int(performance_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(performance_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((performance_overstride_left_raw + performance_overstride_right_raw) / 2))
            html = html.replace('%performance_overstride_description%', description)

        # Protection Overstride values
        protection_overstride_left_raw = result['macro_metric_results']['Protection']['component_scores']['Left Overstride']['micro_metric_score']['raw_value'] 
        protection_overstride_right_raw = result['macro_metric_results']['Protection']['component_scores']['Right Overstride']['micro_metric_score']['raw_value'] 
        protection_overstride_left_elite = result['macro_metric_results']['Protection']['component_scores']['Left Overstride']['micro_metric_score']['elite_score'] 
        protection_overstride_right_elite = result['macro_metric_results']['Protection']['component_scores']['Right Overstride']['micro_metric_score']['elite_score'] 
        protection_overstride_left_score = result['macro_metric_results']['Protection']['component_scores']['Left Overstride']['micro_metric_score']['score'] 
        protection_overstride_right_score = result['macro_metric_results']['Protection']['component_scores']['Right Overstride']['micro_metric_score']['score'] 
        protection_overstride_left_weight = protection_overstride_left_elite / protection_overstride_left_raw * 100
        protection_overstride_right_weight = protection_overstride_right_elite / protection_overstride_right_raw * 100

        protection_overstride_elite = (protection_overstride_left_elite + protection_overstride_right_elite) / 2
        protection_overstride_score = (protection_overstride_left_score + protection_overstride_right_score) / 2
        protection_overstride_left_graph_height = 0.25 * protection_overstride_left_raw
        protection_overstride_right_graph_height = 0.25 * protection_overstride_right_raw
        protection_overstride_elite_graph_height = 0.25 * protection_overstride_elite
        protection_overstride_left_margin = 160 - 28 - protection_overstride_left_graph_height
        protection_overstride_right_margin = 160 - 28 - protection_overstride_right_graph_height
        protection_overstride_elite_margin = 160 - 28 - protection_overstride_elite_graph_height

        protection_overstride_value = convert_to_int((protection_overstride_left_weight + protection_overstride_right_weight) / 2)

        html = html.replace('%protection_overstride_left_raw%', convert_to_int(protection_overstride_left_raw))
        html = html.replace('%protection_overstride_right_raw%', convert_to_int(protection_overstride_right_raw))
        html = html.replace('%protection_overstride_left_graph_height%', convert_to_int(protection_overstride_left_graph_height))
        html = html.replace('%protection_overstride_right_graph_height%', convert_to_int(protection_overstride_right_graph_height))
        html = html.replace('%protection_overstride_left_margin%', convert_to_int(protection_overstride_left_margin))
        html = html.replace('%protection_overstride_right_margin%', convert_to_int(protection_overstride_right_margin))
        html = html.replace('%protection_overstride_elite_margin%', convert_to_int(protection_overstride_elite_margin))
        html = html.replace('%protection_overstride_elite_graph_height%', convert_to_int(protection_overstride_elite_graph_height))
        html = html.replace('%protection_overstride_value%', convert_to_int(protection_overstride_value))
        html = html.replace('%protection_overstride_elite%', convert_to_int(protection_overstride_elite))
        html = html.replace('%protection_overstride_score%', convert_to_int(protection_overstride_score))
        
        if int((protection_overstride_left_raw + protection_overstride_right_raw) / 2) > int(protection_overstride_elite):
            description = overstride_str1
            description = description.replace('%score%', str(int(protection_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((protection_overstride_left_raw + protection_overstride_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int(int((protection_overstride_left_raw + protection_overstride_right_raw) / 2) - int(protection_overstride_elite)))
            description = description.replace('%percent%', str(int((((protection_overstride_left_raw + protection_overstride_right_raw) / 2) - protection_overstride_elite) / ((protection_overstride_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(protection_overstride_elite))
            html = html.replace('%protection_overstride_description%', description)
        elif int((protection_overstride_left_raw + protection_overstride_right_raw) / 2) < int(protection_overstride_elite):
            description = overstride_str2
            description = description.replace('%score%', str(int(protection_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((protection_overstride_left_raw + protection_overstride_right_raw) / 2))
            description = description.replace('%minus_score%', convert_to_int(int(protection_overstride_elite) - int((protection_overstride_left_raw + protection_overstride_right_raw) / 2)))
            description = description.replace('%percent%', str(int((protection_overstride_elite - ((protection_overstride_left_raw + protection_overstride_right_raw) / 2)) / ((protection_overstride_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(protection_overstride_elite))
            html = html.replace('%protection_overstride_description%', description)
        else:
            description = overstride_str3
            description = description.replace('%score%', str(int(protection_overstride_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_overstride_score))
            description = description.replace('%raw_value%', convert_to_int((protection_overstride_left_raw + protection_overstride_right_raw) / 2))
            html = html.replace('%protection_overstride_description%', description)

        # protection Vertical Oscillation values
        protection_vertical_raw = result['macro_metric_results']['Protection']['component_scores']['Vertical Oscillation']['micro_metric_score']['raw_value']
        protection_vertical_elite = result['macro_metric_results']['Protection']['component_scores']['Vertical Oscillation']['micro_metric_score']['elite_score']
        protection_vertical_score = result['macro_metric_results']['Protection']['component_scores']['Vertical Oscillation']['micro_metric_score']['score']
        protection_vertical_weight = protection_vertical_elite / protection_vertical_raw * 100
        protection_vertical_graph_height = 0.25 * protection_vertical_raw
        protection_vertical_elite_graph_height = 0.25 * protection_vertical_elite
        protection_vertical_margin = 160 - 28 - protection_vertical_graph_height
        protection_vertical_elite_margin = 160 - 28 - protection_vertical_elite_graph_height

        html = html.replace('%protection_vertical_weight%', convert_to_int(protection_vertical_weight))
        html = html.replace('%protection_vertical_elite%', convert_to_int(protection_vertical_elite))
        html = html.replace('%protection_vertical_raw%', convert_to_int(protection_vertical_raw))
        html = html.replace('%protection_vertical_graph_height%', convert_to_int(protection_vertical_graph_height))
        html = html.replace('%protection_vertical_elite_graph_height%', convert_to_int(protection_vertical_elite_graph_height))
        html = html.replace('%protection_vertical_margin%', convert_to_int(protection_vertical_margin))
        html = html.replace('%protection_vertical_elite_margin%', convert_to_int(protection_vertical_elite_margin))
        html = html.replace('%protection_vertical_score%', convert_to_int(protection_vertical_score))

        if int(protection_vertical_raw) > int(protection_vertical_elite):
            description = vertical_str1
            description = description.replace('%score%', str(int(protection_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(protection_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(protection_vertical_raw) - int(protection_vertical_elite)))
            description = description.replace('%percent%', str(int((protection_vertical_raw - protection_vertical_elite) / ((protection_vertical_elite) / 100))))
            html = html.replace('%protection_vertical_description%', description)
        elif int(protection_vertical_raw) < int(protection_vertical_elite):
            description = vertical_str2
            description = description.replace('%score%', str(int(protection_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(protection_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(protection_vertical_elite) - int(protection_vertical_raw)))
            description = description.replace('%percent%', str(int((protection_vertical_elite - protection_vertical_raw) / ((protection_vertical_elite) / 100))))
            html = html.replace('%protection_vertical_description%', description)
        else:
            description = vertical_str3
            description = description.replace('%score%', str(int(protection_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(protection_vertical_raw))
            html = html.replace('%protection_vertical_description%', description)

        # protection Cadence values
        protection_cadence_raw = result['macro_metric_results']['Protection']['component_scores']['Cadence']['micro_metric_score']['raw_value']
        protection_cadence_elite = result['macro_metric_results']['Protection']['component_scores']['Cadence']['micro_metric_score']['elite_score']
        protection_cadence_score = result['macro_metric_results']['Protection']['component_scores']['Cadence']['micro_metric_score']['score']
        protection_cadence_weight = protection_cadence_elite / protection_cadence_raw * 100
        
        protection_cadence_graph_height = 0.25 * protection_cadence_raw
        protection_cadence_margin = 160 - 28 - protection_cadence_graph_height
        protection_cadence_elite_graph_height = 0.25 * protection_cadence_elite
        protection_cadence_elite_margin = 160 - 28 - protection_cadence_elite_graph_height

        html = html.replace('%protection_cadence_weight%', convert_to_int(protection_cadence_weight))
        html = html.replace('%protection_cadence_raw%', convert_to_int(protection_cadence_raw))
        html = html.replace('%protection_cadence_graph_height%', convert_to_int(protection_cadence_graph_height))
        html = html.replace('%protection_cadence_margin%', convert_to_int(protection_cadence_margin))
        html = html.replace('%protection_cadence_elite%', convert_to_int(protection_cadence_elite))
        html = html.replace('%protection_cadence_elite_graph_height%', convert_to_int(protection_cadence_elite_graph_height))
        html = html.replace('%protection_cadence_elite_margin%', convert_to_int(protection_cadence_elite_margin))
        html = html.replace('%protection_cadence_score%', convert_to_int(protection_cadence_score))

        if int(protection_cadence_raw) > int(protection_cadence_elite):
            description = cadence_str1
            description = description.replace('%score%', str(int(protection_cadence_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_cadence_score))
            description = description.replace('%raw_value%', convert_to_int(protection_cadence_raw))
            description = description.replace('%minus_score%', convert_to_int(int(protection_cadence_raw) - int(protection_cadence_elite)))
            description = description.replace('%percent%', str(int((protection_cadence_raw - protection_cadence_elite) / ((protection_cadence_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(protection_cadence_elite))
            html = html.replace('%protection_cadence_description%', description)
        elif int(protection_cadence_raw) < int(protection_cadence_elite):
            description = cadence_str2
            description = description.replace('%score%', str(int(protection_cadence_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_cadence_score))
            description = description.replace('%raw_value%', convert_to_int(protection_cadence_raw))
            description = description.replace('%minus_score%', convert_to_int(int(protection_cadence_elite) - int(protection_cadence_raw)))
            description = description.replace('%percent%', str(int((protection_cadence_elite - protection_cadence_raw) / ((protection_cadence_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(protection_cadence_elite))
            html = html.replace('%protection_cadence_description%', description)
        else:
            description = cadence_str3
            description = description.replace('%score%', str(int(protection_cadence_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(protection_cadence_score))
            description = description.replace('%raw_value%', convert_to_int(protection_cadence_raw))
            description = description.replace('%elite_score%', convert_to_int(protection_cadence_elite))
            html = html.replace('%protection_cadence_description%', description)

        # Efficiency Vertical Stiffness values
        efficiency_stiffness_raw = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Stiffness']['micro_metric_score']['raw_value']
        efficiency_stiffness_elite = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Stiffness']['micro_metric_score']['elite_score']
        efficiency_stiffness_score = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Stiffness']['micro_metric_score']['score']
        efficiency_stiffness_weight = efficiency_stiffness_elite / efficiency_stiffness_raw * 100
        efficiency_stiffness_graph_height = 0.25 * efficiency_stiffness_raw * 10
        efficiency_stiffness_margin = 160 - 28 - efficiency_stiffness_graph_height
        efficiency_stiffness_elite_graph_height = 0.25 * efficiency_stiffness_elite * 10
        efficiency_stiffness_elite_margin = 160 - 28 - efficiency_stiffness_elite_graph_height

        html = html.replace('%efficiency_stiffness_weight%', convert_to_int(efficiency_stiffness_weight))
        html = html.replace('%efficiency_stiffness_raw%', convert_to_int(efficiency_stiffness_raw))
        html = html.replace('%efficiency_stiffness_graph_height%', convert_to_int(efficiency_stiffness_graph_height))
        html = html.replace('%efficiency_stiffness_margin%', convert_to_int(efficiency_stiffness_margin))
        html = html.replace('%efficiency_stiffness_elite%', convert_to_int(efficiency_stiffness_elite))
        html = html.replace('%efficiency_stiffness_elite_graph_height%', convert_to_int(efficiency_stiffness_elite_graph_height))
        html = html.replace('%efficiency_stiffness_elite_margin%', convert_to_int(efficiency_stiffness_elite_margin))
        html = html.replace('%efficiency_stiffness_score%', convert_to_int(efficiency_stiffness_score))

        if int(efficiency_stiffness_raw) > int(efficiency_stiffness_elite):
            description = stiffness_str1
            description = description.replace('%score%', str(int(efficiency_stiffness_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_stiffness_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_stiffness_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_stiffness_raw) - int(efficiency_stiffness_elite)))
            description = description.replace('%percent%', str(int((efficiency_stiffness_raw - efficiency_stiffness_elite) / ((efficiency_stiffness_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(efficiency_stiffness_elite))
            html = html.replace('%efficiency_stiffness_description%', description)
        elif int(efficiency_stiffness_raw) < int(efficiency_stiffness_elite):
            description = stiffness_str2
            description = description.replace('%score%', str(int(efficiency_stiffness_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_stiffness_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_stiffness_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_stiffness_elite) - int(efficiency_stiffness_raw)))
            description = description.replace('%percent%', str(int((efficiency_stiffness_elite - efficiency_stiffness_raw) / ((efficiency_stiffness_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(efficiency_stiffness_elite))
            html = html.replace('%efficiency_stiffness_description%', description)
        else:
            description = stiffness_str3
            description = description.replace('%score%', str(int(efficiency_stiffness_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_stiffness_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_stiffness_raw))
            description = description.replace('%elite_score%', convert_to_int(efficiency_stiffness_elite))
            html = html.replace('%efficiency_stiffness_description%', description)

        # Efficiency Braking Power values
        efficiency_braking_raw = result['macro_metric_results']['Efficiency']['component_scores']['Braking Power']['micro_metric_score']['raw_value']
        efficiency_braking_elite = result['macro_metric_results']['Efficiency']['component_scores']['Braking Power']['micro_metric_score']['elite_score']
        efficiency_braking_score = result['macro_metric_results']['Efficiency']['component_scores']['Braking Power']['micro_metric_score']['score']
        efficiency_braking_weight = efficiency_braking_elite / efficiency_braking_raw * 100
        efficiency_braking_graph_height = 0.25 * efficiency_braking_raw * 10
        efficiency_braking_margin = 160 - 28 - efficiency_braking_graph_height
        efficiency_braking_elite_graph_height = 0.25 * efficiency_braking_elite * 10
        efficiency_braking_elite_margin = 160 - 28 - efficiency_braking_elite_graph_height

        html = html.replace('%efficiency_braking_weight%', convert_to_int(efficiency_braking_weight))
        html = html.replace('%efficiency_braking_raw%', convert_to_int(efficiency_braking_raw))
        html = html.replace('%efficiency_braking_graph_height%', convert_to_int(efficiency_braking_graph_height))
        html = html.replace('%efficiency_braking_margin%', convert_to_int(efficiency_braking_margin))
        html = html.replace('%efficiency_braking_elite%', convert_to_int(efficiency_braking_elite))
        html = html.replace('%efficiency_braking_elite_graph_height%', convert_to_int(efficiency_braking_elite_graph_height))
        html = html.replace('%efficiency_braking_elite_margin%', convert_to_int(efficiency_braking_elite_margin))
        html = html.replace('%efficiency_braking_score%', convert_to_int(efficiency_braking_score))

        if int(efficiency_braking_raw) > int(efficiency_braking_elite):
            description = braking_str1
            description = description.replace('%score%', str(int(efficiency_braking_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_braking_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_braking_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_braking_raw) - int(efficiency_braking_elite)))
            description = description.replace('%percent%', str(int((efficiency_braking_raw - efficiency_braking_elite) / ((efficiency_braking_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(efficiency_braking_elite))
            html = html.replace('%efficiency_braking_description%', description)
        elif int(efficiency_braking_raw) < int(efficiency_braking_elite):
            description = braking_str2
            description = description.replace('%score%', str(int(efficiency_braking_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_braking_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_braking_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_braking_elite) - int(efficiency_braking_raw)))
            description = description.replace('%percent%', str(int((efficiency_braking_elite - efficiency_braking_raw) / ((efficiency_braking_elite) / 100))))
            description = description.replace('%elite_score%', convert_to_int(efficiency_braking_elite))
            html = html.replace('%efficiency_braking_description%', description)
        else:
            description = braking_str3
            description = description.replace('%score%', str(int(efficiency_braking_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_braking_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_braking_raw))
            description = description.replace('%elite_score%', convert_to_int(efficiency_braking_elite))
            html = html.replace('%efficiency_braking_description%', description)

        # Efficiency Vertical Oscillation values
        efficiency_vertical_raw = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Oscillation']['micro_metric_score']['raw_value']
        efficiency_vertical_elite = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Oscillation']['micro_metric_score']['elite_score']
        efficiency_vertical_score = result['macro_metric_results']['Efficiency']['component_scores']['Vertical Oscillation']['micro_metric_score']['score']
        efficiency_vertical_weight = efficiency_vertical_elite / efficiency_vertical_raw * 100
        efficiency_vertical_graph_height = 0.25 * efficiency_vertical_raw * 2
        efficiency_vertical_margin = 160 - 28 - efficiency_vertical_graph_height
        efficiency_vertical_elite_graph_height = 0.25 * efficiency_vertical_elite * 2
        efficiency_vertical_elite_margin = 160 - 28 - efficiency_vertical_elite_graph_height

        html = html.replace('%efficiency_vertical_weight%', convert_to_int(efficiency_vertical_weight))
        html = html.replace('%efficiency_vertical_raw%', convert_to_int(efficiency_vertical_raw))
        html = html.replace('%efficiency_vertical_graph_height%', convert_to_int(efficiency_vertical_graph_height))
        html = html.replace('%efficiency_vertical_margin%', convert_to_int(efficiency_vertical_margin))
        html = html.replace('%efficiency_vertical_elite%', convert_to_int(efficiency_vertical_elite))
        html = html.replace('%efficiency_vertical_elite_graph_height%', convert_to_int(efficiency_vertical_elite_graph_height))
        html = html.replace('%efficiency_vertical_elite_margin%', convert_to_int(efficiency_vertical_elite_margin))
        html = html.replace('%efficiency_vertical_score%', convert_to_int(efficiency_vertical_score))

        if int(efficiency_vertical_raw) > int(efficiency_vertical_elite):
            description = vertical_str1
            description = description.replace('%score%', str(int(efficiency_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_vertical_raw) - int(efficiency_vertical_elite)))
            description = description.replace('%percent%', str(int((efficiency_vertical_raw - efficiency_vertical_elite) / ((efficiency_vertical_elite) / 100))))
            html = html.replace('%efficiency_vertical_description%', description)
        elif int(efficiency_vertical_raw) < int(efficiency_vertical_elite):
            description = vertical_str2
            description = description.replace('%score%', str(int(efficiency_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_vertical_raw))
            description = description.replace('%minus_score%', convert_to_int(int(efficiency_vertical_elite) - int(efficiency_vertical_raw)))
            description = description.replace('%percent%', str(int((efficiency_vertical_elite - efficiency_vertical_raw) / ((efficiency_vertical_elite) / 100))))
            html = html.replace('%efficiency_vertical_description%', description)
        else:
            description = vertical_str3
            description = description.replace('%score%', str(int(efficiency_vertical_score)) + "/10")
            description = description.replace('%recommendation_value%', get_recommedation_value(efficiency_vertical_score))
            description = description.replace('%raw_value%', convert_to_int(efficiency_vertical_raw))
            html = html.replace('%efficiency_vertical_description%', description)

        html = html.replace('%brand%', result['shoe_brand'])
        html = html.replace('%model%', result['shoe_name'])
        html = html.replace('%size%', result['shoe_size'])
        
        first_name = customer.get('first_name', '')
        last_name = customer.get('last_name', '')
        html = html.replace('%username%', first_name + ' ' + last_name)
        
        html = html.replace('%bmi%', convert_to_int(result['raw_metrics']['Body Mass Index']['median']))
        html = html.replace('%running_speed%', convert_to_int(result['raw_metrics']['Running Speed']['median']))

        dateTime = result['recording_date']
        unix_timestamp = dateTime / 1000
        date_time = datetime.fromtimestamp(unix_timestamp)
        formatted_date = date_time.strftime("%d/%m/%Y")
        formatted_time = date_time.strftime("%H:%M")
        html = html.replace('%date%', formatted_date)
        html = html.replace('%time%', formatted_time)
        html = html.replace('%height%', str(int(customer['height_mm'] / 10)))
        html = html.replace('%weight%', str(int(customer['weight_g'] / 1000)))

        branch_id = user['branch_id']
        branchList = branch_company['branches']
        branch_obj = {}
        for obj in branchList:
            if obj['branch_id'] == branch_id:
                    branch_obj = obj

        html = html.replace("%company_name%", str(companies['name']))

        # Get the company addresses with safe defaults
        address_1 = companies['address'][0] if len(companies['address']) > 0 else ''
        address_2 = companies['address'][1] if len(companies['address']) > 1 else ''
        address_3 = companies['address'][2] if len(companies['address']) > 2 else ''

        # Replace the placeholders in the HTML
        html = html.replace("%company_address_1%", address_1)
        html = html.replace("%company_address_2%", address_2)
        html = html.replace("%company_address_3%", address_3)

        if not companies.get('file_name'):
            companies['file_name'] = "default.png"
        html = html.replace("%company_logo%", companies['file_name'])
        # html = html.replace("%company_phone_number%", companies['phone_number'])     
        html = html.replace("%company_phone_number%", branch_obj['phone_number'])

        full_shop_name = str(companies['name']) + ' ' + str(branch_obj['name'])
        html = html.replace("%shop%", full_shop_name)    

        html = html.replace("%running_shop%", full_shop_name)
        html = html.replace("%running_contact_info_name%", full_shop_name)
        html = html.replace("%running_contact_info_address%", branch_obj['address'][0])
        html = html.replace("%running_contact_info_phone%", branch_obj['phone_number'])

        # file_path = f"/home/neymar/AvaAdmin/data/temp_email/file_{dateTime}.html"
        file_path = f"/home/AvaAdmin/data/temp_email/file_{dateTime}.html"
        save_html_to_file(html, file_path)

        # send_email_with_html_attachment('skyisveryblue1@gmail.com', 'Customer Report', file_path)
        send_email_with_html_attachment('jonathan@mar-systems.co.uk', 'Customer Report', file_path)
        if (
            customer.get('email') is not None and
            'purchase_decision' in result and
            'decision' in result['purchase_decision'] and
            result['purchase_decision']['decision'] == 1
        ):
            send_email_with_html_attachment(customer['email'], 'Customer Report', file_path)
        return messages_pb2.DashboardReport(aged_sales_count=0)

    def GetData(self, request: messages_pb2.DataRequest, context) -> messages_pb2.DataResponse:
        certFile = '/etc/letsencrypt/live/api.runright.io/cert.pem'
        fullChainFile = '/etc/letsencrypt/live/api.runright.io/fullchain.pem'

        # cert.pem file check start
        with open(certFile, 'rb') as pem_file:
            pem_data = pem_file.read()
        
        certificate = x509.load_pem_x509_certificate(pem_data, default_backend())
        
        expiration_date = certificate.not_valid_after
        current_date = datetime.utcnow()
        
        print(f"Cert Certificate Expiration Date: {expiration_date}")
        # cert.pem file check end

        # fullchain.pem file check start
        with open(fullChainFile, 'rb') as pem_file:
            fullChainPem_data = pem_file.read()
        
        full_chain_certificate = x509.load_pem_x509_certificate(fullChainPem_data, default_backend())
        
        full_chain_expiration_date = full_chain_certificate.not_valid_after
        
        print(f"FullChain Certificate Expiration Date: {full_chain_expiration_date}")
        # fullchain.pem file check end


        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        result = messages_pb2.DataResponse()
        result.total_disk = f"{disk.total / (1024 ** 3):.2f}"
        result.free_disk = f"{disk.free / (1024 ** 3):.2f}"
        result.used_disk = f"{disk.used / (1024 ** 3):.2f}"
        result.disk_percent = f"{disk.percent}"
        result.total_memory = f"{memory.total / (1024 ** 3):.2f}"
        result.free_memory = f"{memory.free / (1024 ** 3):.2f}"
        result.used_memory = f"{memory.used / (1024 ** 3):.2f}"
        result.memory_percent = f"{memory.percent}"
        result.cert_valid = f"{expiration_date}"
        result.cert = pem_data
        result.fullchain_valid = f"{full_chain_expiration_date}"
        result.fullchain = fullChainPem_data
        return result