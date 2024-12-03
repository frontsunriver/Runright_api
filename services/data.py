import unittest
from copy import deepcopy
from datetime import datetime
from json import loads

import grpc
import proto.messages_pb2 as messages_pb2
import proto.messages_pb2_grpc as messages_pb2_grpc
from bson import ObjectId
from bson.errors import InvalidId
from decorators.required_role import check_role, check_user_role
from lib.converter import protobuf_to_dict
from lib.query_utils import (add_creation_attrs, cms_to_mongo, cms_to_shoeModel,
                             restrict_to_company, skip_and_limit, sort_cursor, convert_to_int, save_html_to_file, get_recommedation_value)
from lib.emai import send_email_with_html_attachment
from lib.timestamp import now
from pymongo.database import Database


class DataServicer(messages_pb2_grpc.DataServicer):
    def __init__(self, db: Database):
        self.db = db

    @check_role([6, 5, 2])
    def setMetricMapping(self, request, context):
        data = protobuf_to_dict(request, including_default_value_fields=True)
        data['bin'] = request.SerializeToString()
        add_creation_attrs(data, context)
        if data['version'] is None:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'Version is a required attribute for metric mapping')
            return

        if not data['version']:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'Version must be greater than 0')
            return

        existing = self.db.metricMappings.find_one(
            {'version': data['version']})
        if existing:
            context.abort(grpc.StatusCode.ALREADY_EXISTS,
                          'A metric mapping already exists with this version')
            return

        res = self.db.metricMappings.insert_one(data)
        return messages_pb2.CMSResult(string_result=str(res.inserted_id))

    def getMetricMapping(self, request, context):
        query = cms_to_mongo(request)
        metric_mappings = self.db.metricMappings.find(query)
        skip_and_limit(request, metric_mappings)
        for x in metric_mappings:
            msg = messages_pb2.MetricMappingMsg()
            msg.ParseFromString(x['bin'])
            msg.created = x['created']
            yield msg

    def getLatestMetricMapping(self, request, context):
        doc = list(self.db.metricMappings.find(
            {}).sort([("version", -1)]).limit(1))[0]
        if not doc:
            context.abort(grpc.StatusCode.NOT_FOUND,
                          'No results found for this query')
            return
        else:
            del doc['_id']
            del doc['bin']
            return messages_pb2.MetricMappingMsg(**doc)

    def countShoeTrialResults(self, request, context):
        # Filter by start and end millis if provided in request
        query = cms_to_mongo(request)

        # Restrict by company if not an admin
        if not context.user['role'] in [6, 5]:
            restrict_to_company(query, context)

        # Get results
        count = self.db.shoeTrialResults.count(query)

        return messages_pb2.CMSResult(int_result=count)

    def setShoeTrialResult(self, request, context):
        if len(request.recording_id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'shoeTrialResults cannot be updated')
            return

        if not len(request.customer_id):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'customer_id is a mandatory field')
            return

        try:
            matching_customer_count = self.db.customers.count(
                {'_id': ObjectId(request.customer_id)})
        except InvalidId:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'customer_id specified does not exist')
            return

        if not matching_customer_count:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'customer_id specified does not exist')
            return

        request.technician_id = str(context.user['_id'])
        request.company_id = str(context.user['company_id'])
        request.branch_id = str(context.user['branch_id'])

        if not self.db.companies.count({'_id': ObjectId(request.company_id), 'branches.devices.device_id': request.device_id}):
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'specified device_id does not exist')
            return

        serialised = request.SerializeToString()
        data = protobuf_to_dict(request, including_default_value_fields=True)
        add_creation_attrs(data, context)

        if 'recording_id' in data:
            del data['recording_id']

        mongoid = ObjectId()
        # Store message encoded in bin attribute
        data['bin'] = serialised
        res = self.db.shoeTrialResults.update_one(
            {'_id': mongoid}, {'$set': data}, True)


        #####################################################################################


        user_company_id = context.user['company_id']
        role_company = self.db.companies.find_one({"_id": ObjectId(user_company_id)})

        licence_expiry = role_company.get('licence_expiry')
        type_val = role_company.get('type')
        sendingEmailConfig = False
        if type_val is not None: 
            if type_val != 'lite':
                if licence_expiry is not None:
                    date_from_value = datetime.fromtimestamp(licence_expiry / 1000.0)

                    # Get the current date and time
                    current_date = datetime.now()

                    # Compare the two dates
                    is_current_date_smaller = current_date < date_from_value

                    if is_current_date_smaller:
                        sendingEmailConfig = True
                    else:
                        sendingEmailConfig = False
                else:
                    print("Licence expiry date is None")
                    sendingEmailConfig = False
            else: 
                sendingEmailConfig = False
        else:
            sendingEmailConfig = False

        if sendingEmailConfig:

            result = self.db.shoeTrialResults.find_one({"_id": mongoid})
            customer = self.db.customers.find_one({"_id": ObjectId(result['customer_id'])})
            user = self.db.users.find_one({"_id": ObjectId(result['technician_id'])})
            branch_company = self.db.companies.find_one({"_id": ObjectId(user['company_id'])})
            companies = self.db.companies.find_one({"_id": ObjectId(result['company_id'])})


            with open("/home/AvaAdmin/data/temp_email/template.html", 'r', encoding='utf-8') as file:
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

        #####################################################################################

        if res.modified_count:
            return messages_pb2.CMSResult()
        elif res.upserted_id:
            return messages_pb2.CMSResult(string_result=str(res.upserted_id))

    def getShoeTrialResults(self, request, context):
        # Filter by start and end millis if provided in request
        query = cms_to_mongo(request)

        # Restrict by company if not an admin
        if not context.user['role'] in [6, 5]:
            restrict_to_company(query, context)

        # Get results
        shoe_trial_results = self.db.shoeTrialResults.find(query)
        sort_cursor(request, shoe_trial_results, ['created', 'updated'])
        skip_and_limit(request, shoe_trial_results)

        # Iterate and yield
        for x in shoe_trial_results:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.created = x['created']
            yield msg

    def getShoeTrialResultsByCustomerId(self, request: messages_pb2.CMSQuery, context):
        query = cms_to_mongo(request)
        query = restrict_to_company(query, context)
        query['customer_id'] = request.string_query

        shoe_trial_results = self.db.shoeTrialResults.find(query)
        sort_cursor(request, shoe_trial_results, ['created', 'updated'])
        skip_and_limit(request, shoe_trial_results)
        for x in shoe_trial_results:
            msg = messages_pb2.ShoeTrialResult()
            msg.ParseFromString(x['bin'])
            msg.recording_id = str(x['_id'])
            msg.created = x['created']
            yield msg

    def getMinifiedResultsByCustomerId(self, request: messages_pb2.CMSQuery, context):
        query = cms_to_mongo(request)
        query = restrict_to_company(query, context)
        query['customer_id'] = request.string_query
        shoe_trial_results = self.db.shoeTrialResults.find(
            query, {'micro_metric_scores': 0, 'body_frames': 0, 'alignment': 0, 'qa_msg': 0, 'capture_engine_version': 0, 'recording_filename': 0})
        sort_cursor(request, shoe_trial_results, ['created', 'updated'])
        skip_and_limit(request, shoe_trial_results)
        for x in shoe_trial_results:
            del x['bin']
            if 'customer' in x:
                del x['customer']
            macro_metric_results = x['macro_metric_results']
            del x['macro_metric_results']
            raw_metrics = x['raw_metrics']
            del x['raw_metrics']
            x['recording_id'] = str(x['_id'])
            del x['_id']
            del x['creator']

            in_message = messages_pb2.ShoeTrialResult(**x)

            for name, value in macro_metric_results.items():
                in_message.macro_metric_results[name]
                for comp, comp_val in value['component_scores'].items():
                    in_message.macro_metric_results[name].component_scores[comp]
                    component_score = messages_pb2.ComponentScore(
                        **comp_val)
                    in_message.macro_metric_results[name].component_scores[comp].MergeFrom(
                        component_score)
                del value['component_scores']

                macro_metric_result = messages_pb2.MacroMetricResult(
                    **value)
                in_message.macro_metric_results[name].MergeFrom(
                    macro_metric_result)

            for name, value in raw_metrics.items():
                in_message.raw_metrics[name]
                raw_metric = messages_pb2.RawMetric(**value)
                in_message.raw_metrics[name].MergeFrom(raw_metric)
            yield in_message

    def countShoeTrialResultsByCustomerId(self, request: messages_pb2.CMSQuery, context):
        query = cms_to_mongo(request)
        query = restrict_to_company(query, context)
        query['customer_id'] = request.string_query

        count = self.db.shoeTrialResults.count(query)
        return messages_pb2.CMSResult(int_result=count)

    @check_role([5, 6, 4, 3, 2])
    def deleteShoeTrialResult(self, request: messages_pb2.CMSQuery, context):
        if not request.string_query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          'recording_id is required')
            return
        else:
            try:
                res = self.db.shoeTrialResults.delete_one(
                    {'_id': ObjectId(request.string_query)})
            except InvalidId:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                              'Invalid recording_id')
                return
            return messages_pb2.CMSResult(int_result=res.deleted_count)
