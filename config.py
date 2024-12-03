from json import loads
import os.path

def get_config():
    with open('settings.json') as f:
        config = loads(f.read())
    
    if os.path.isfile('settings.local.json'):
        with open('settings.local.json') as g:
            local_config = loads(g.read())
            for key, value in local_config.items():
                config[key] = value

    return config