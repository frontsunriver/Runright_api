import csv
from datetime import datetime
from json import loads


mappings = {
    'created': 'Recording Date',
    'shoe_brand': 'Shoe Brand',
    'shoe_name': 'Shoe Name',
    'shoe_size': 'Shoe Size',
    'raw_metrics.Body Mass Index.median': 'Body Mass Index',
    'raw_metrics.Running Speed.median': 'Treadmill Speed',
    'raw_metrics.Cadence.median': 'Cadence',
    'raw_metrics.Dynamic Balance.median': "Dynamic Balance (Single Dial)",
    "raw_metrics.Left Overstride.median": "Overstride Left",
    "raw_metrics.Right Overstride.median": "Overstride Right",
    "raw_metrics.Left Knee Flexion.median": "Knee Flexion Left",
    "raw_metrics.Right Knee Flexion.median": "Knee Flexion Right",
    "raw_metrics.Left Hip Drop.median": "Hip Drop Left",
    "raw_metrics.Right Hip Drop.median": "Hip Drop Right",
    "raw_metrics.Left Step Separation.median": "Step Separation Left",\
    "raw_metrics.Right Step Separation.median": "Step Separation Right",
    "raw_metrics.Left Knee Stability.median": "Knee Stability Left",
    "raw_metrics.Right Knee Stability.median": "Knee Stability Right",
    "raw_metrics.Left Ground Contact.median": "Ground Contact Time Left",
    "raw_metrics.Right Ground Contact.median": "Ground Contact Time Right",
    "raw_metrics.Braking Power.median": "Braking Power",
    "raw_metrics.Vertical Stiffness.median": "Vertical Stiffness",
    "raw_metrics.Flight Time.median": "Flight Time",
    "raw_metrics.Duty Factor.median": "Duty Factor",
    "raw_metrics.Vertical Oscillation.median": "Vertical Oscillation (Single Dial)",
    "macro_metric_results.Performance.score": "Performance Score",
    "macro_metric_results.Performance.grade": "Performance Grade",
    "macro_metric_results.Rideability.score": "Rideability Score",
    "macro_metric_results.Rideability.grade": "Rideability Grade",
    "macro_metric_results.Efficiency.score": "Efficiency Score",
    "macro_metric_results.Efficiency.grade": "Efficiency Grade",
    "macro_metric_results.Protection.score": "Protection Score",
    "macro_metric_results.Protection.grade": "Protection Grade",
}

def get_customer_by_id(customers, customer_id):
    for x in customers:
        if str(x['_id']['$oid']) == customer_id:
            return x

    return None


with open('json_data/shoeTrialResults.json', 'r') as shoeTrialDataFile:
    shoe_trial_results = loads(shoeTrialDataFile.read())

with open('json_data/customers.json', 'r') as customerDataFile:
    customers = loads(customerDataFile.read())

with open('shoeTrialResults.csv', 'w') as f:
    output = csv.DictWriter(f, ['Customer Name'] + list(mappings.values()))
    output.writeheader()
    for result in shoe_trial_results:
        row_values = {}
        customer = get_customer_by_id(customers, result['customer_id'])
        if customer is not None:
            row_values['Customer Name'] = customer['first_name'] + ' ' +  customer['last_name']
        for key in mappings.keys():
            accessor = result
            for part in key.split('.'):
                accessor = accessor[part]
            if part == 'created':
                accessor = datetime.fromtimestamp(accessor/1000.0).strftime('%d/%m/%Y')
            try:
                accessor = round(float(accessor), 3)
            except:
                pass
            row_values[mappings[key]] = accessor

        output.writerow(row_values)
