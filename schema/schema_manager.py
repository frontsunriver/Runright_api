from pymongo.database import Database
import os 
import re
from importlib.util import spec_from_file_location, module_from_spec

class SchemaManager():
    def __init__(self, db: Database):
        self.db = db
        self.schema_dir_path = os.path.dirname(os.path.realpath(__file__))

    def check_and_update_schema(self):
        print('Checking DB Schema Version')
        self.current_version = self._get_current_schema_version()
        schema_files = self._get_schema_files()

        for x in schema_files:
            if self._check_schema_file(x):
                version = x.split('.')[0]
                print(f'Updating Schema to {version}')
                self._execute_schema_file(x)
        print('Schema is up to date')

    def _get_current_schema_version(self):
        setting = self.db.schema.find_one({'name': 'schema'})
        if not setting:
            if self._create_schema_doc():
                return self._get_current_schema_version()
            else:
                raise Exception('Unable to create schema version doc')
        
        return int(setting['value'])

    def _get_schema_files(self):
        schema_dir_list = os.listdir(self.schema_dir_path)
        schema_files = [x for x in schema_dir_list if re.match(r'.*v[0-9]{3,}\.(js|py)', x)]
        schema_files.sort()
        return schema_files

    def _get_version_number_from_path(self, file_path):
        matches = re.findall(r'.*v([0-9]{3,})\.(?:js|py)', file_path)
        if matches:
            return int(matches[0])
        else:
            return False

    def _check_schema_file(self, file_path):
        version = self._get_version_number_from_path(file_path)
        return version > self.current_version    

    def _create_schema_doc(self):
        res = self.db.schema.insert_one({'name': 'schema', 'value': 0})
        return res.inserted_id
    
    def _execute_schema_file(self, file_name):
        schema_file_path = os.path.join(self.schema_dir_path, file_name)
        if schema_file_path.endswith('.py'):
            self._run_py_schema_file(schema_file_path)
        elif schema_file_path.endswith('.js'):
            self._run_js_schema_file(schema_file_path)
        else:
            file_type = schema_file_path.split('.')[-1]
            raise Exception(f'Unknown schema file type {file_type}')

    def _run_py_schema_file(self, file_path):
        _, filename = os.path.split(file_path)
        basename, _ = os.path.splitext(filename)
        spec = spec_from_file_location(basename, file_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.__name__ == basename
        version = self._get_version_number_from_path(file_path)
        if module.update(self.db):
            self._update_schema_version(version)
        else:
            raise Exception(f'Failed to execute {version}')

    def _update_schema_version(self, new_version):
        self.db.schema.update_one({'name': 'schema'}, {'$set': {'value': new_version}})

    def _run_js_schema_file(self, file_path):
        raise NotImplementedError('JS schema files are not yet supported')
