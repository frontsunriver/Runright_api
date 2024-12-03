from lib.converter import protobuf_to_dict
from services.config import ConfigurationServicer
from proto import messages_pb2
from tests.test_servicer import TestServicer
from tests.utils.testing_context import TestingContext


class TestConfigServicer(TestServicer):
    def setUp(self):
        super().setUp()
        self.servicer = ConfigurationServicer(self.db, {})
        self.db.branch_shoes.remove()

    def test_set_get_CurrentConfigurationSettings_create(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)

        # Lets add some basic values
        in_data = {
            'capture_engine_release_version': 'v1.2.3',
            'capture_engine_beta_version': 'v2.3.4',
            'app_release_version': 'v4.5.0',
            'app_beta_version': 'v24.5',
            'metric_mapping_release_version': 3,
            'metric_mapping_beta_version': 7
        }
        set_message = messages_pb2.ConfigurationSettings(**in_data)
        set_response = self.servicer.setConfigurationSettings(
            set_message, context=admin_context)
        self.assertTrue(set_response.string_result)

        # Now let's try and get it back out again
        get_message = messages_pb2.CMSQuery()
        get_resp = self.servicer.getCurrentConfigurationSettings(
            get_message, context=admin_context)
        # Check data returned mathes that which we inserted
        self.assertDictEqual(protobuf_to_dict(get_resp), in_data)

    def test_setCurrentConfigurationSettings_update(self):
        _, admin = self.data_generator.generate_fake_user(6, None, None)
        admin_context = TestingContext(admin)
        # Lets add some basic values
        in_data = {
            'capture_engine_release_version': 'v1.2.3',
            'capture_engine_beta_version': 'v2.3.4',
            'app_release_version': 'v4.5.0',
            'app_beta_version': 'v24.5',
            'metric_mapping_release_version': 3,
            'metric_mapping_beta_version': 7
        }
        set_message = messages_pb2.ConfigurationSettings(**in_data)
        set_response = self.servicer.setConfigurationSettings(
            set_message, context=admin_context)
        self.assertTrue(set_response.string_result)

        # Now overwrite them
        update_data = {
            'capture_engine_release_version': 'v1.9.3',
            'capture_engine_beta_version': 'v2.3.4',
            'app_release_version': 'v4.5.2',
            'app_beta_version': 'v20.5',
            'metric_mapping_release_version': 2,
            'metric_mapping_beta_version': 4
        }
        update_message = messages_pb2.ConfigurationSettings(**update_data)
        update_response = self.servicer.setConfigurationSettings(
            update_message, context=admin_context)
        self.assertTrue(update_response.string_result)

        # Now let's try and get it back out again
        get_message = messages_pb2.CMSQuery()
        get_resp = self.servicer.getCurrentConfigurationSettings(
            get_message, context=admin_context)
        # Check data returned mathes that which we inserted
        self.assertDictEqual(protobuf_to_dict(get_resp), update_data)
