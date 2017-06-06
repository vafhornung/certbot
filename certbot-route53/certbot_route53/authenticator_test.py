"""Tests for certbot_route53.authenticator"""

import unittest

import mock
from botocore.exceptions import NoCredentialsError, ClientError

from certbot import errors
from certbot.plugins import dns_test_common
from certbot.plugins.dns_test_common import DOMAIN


class AuthenticatorTest(unittest.TestCase, dns_test_common.BaseAuthenticatorTest):
    # pylint: disable=protected-access

    def setUp(self):
        from certbot_route53.authenticator import Authenticator

        super(AuthenticatorTest, self).setUp()

        self.config = mock.MagicMock()

        self.auth = Authenticator(self.config, "route53")

    def test_perform(self):
        self.auth._change_txt_record = mock.MagicMock()
        self.auth._wait_for_change = mock.MagicMock()

        self.auth.perform([self.achall])

        self.auth._change_txt_record.assert_called_once_with("UPSERT",
                                                             '_acme-challenge.' + DOMAIN,
                                                             mock.ANY)
        self.auth._wait_for_change.assert_called_once()

    def test_perform_no_credentials_error(self):
        self.auth._change_txt_record = mock.MagicMock(side_effect=NoCredentialsError)

        self.assertRaises(errors.PluginError,
                          self.auth.perform,
                          [self.achall])

    def test_perform_client_error(self):
        self.auth._change_txt_record = mock.MagicMock(
            side_effect=ClientError({"Error": {"Code": "foo"}}, "bar"))

        self.assertRaises(errors.PluginError,
                          self.auth.perform,
                          [self.achall])

    def test_cleanup(self):
        self.auth._attempt_cleanup = True

        self.auth._change_txt_record = mock.MagicMock()

        self.auth.cleanup([self.achall])

        self.auth._change_txt_record.assert_called_once_with("DELETE",
                                                             '_acme-challenge.'+DOMAIN,
                                                             mock.ANY)

    def test_cleanup_no_credentials_error(self):
        self.auth._attempt_cleanup = True

        self.auth._change_txt_record = mock.MagicMock(side_effect=NoCredentialsError)

        self.auth.cleanup([self.achall])

    def test_cleanup_client_error(self):
        self.auth._attempt_cleanup = True

        self.auth._change_txt_record = mock.MagicMock(
            side_effect=ClientError({"Error": {"Code": "foo"}}, "bar"))

        self.auth.cleanup([self.achall])


class ClientTest(unittest.TestCase):
    # pylint: disable=protected-access

    PRIVATE_ZONE = {
                        "Id": "BAD-PRIVATE",
                        "Name": "example.com",
                        "Config": {
                            "PrivateZone": True
                        }
                    }

    EXAMPLE_NET_ZONE = {
                            "Id": "BAD-WRONG-TLD",
                            "Name": "example.net",
                            "Config": {
                                "PrivateZone": False
                            }
                        }

    EXAMPLE_COM_ZONE = {
                            "Id": "EXAMPLE",
                            "Name": "example.com",
                            "Config": {
                                "PrivateZone": False
                            }
                        }

    FOO_EXAMPLE_COM_ZONE = {
                                "Id": "FOO",
                                "Name": "foo.example.com",
                                "Config": {
                                    "PrivateZone": False
                                }
                            }

    def setUp(self):
        from certbot_route53.authenticator import Authenticator

        super(ClientTest, self).setUp()

        self.config = mock.MagicMock()

        self.client = Authenticator(self.config, "route53")

    def test_find_zone_id_for_domain(self):
        self.client.r53.get_paginator = mock.MagicMock()
        self.client.r53.get_paginator().paginate.return_value = [
            {
                "HostedZones": [
                    self.EXAMPLE_NET_ZONE,
                    self.EXAMPLE_COM_ZONE,
                ]
            }
        ]

        result = self.client._find_zone_id_for_domain("foo.example.com")
        self.assertEqual(result, "EXAMPLE")

    def test_find_zone_id_for_domain_pagination(self):
        self.client.r53.get_paginator = mock.MagicMock()
        self.client.r53.get_paginator().paginate.return_value = [
            {
                "HostedZones": [
                    self.PRIVATE_ZONE,
                    self.EXAMPLE_COM_ZONE,
                ]
            },
            {
                "HostedZones": [
                    self.PRIVATE_ZONE,
                    self.FOO_EXAMPLE_COM_ZONE,
                ]
            }
        ]

        result = self.client._find_zone_id_for_domain("foo.example.com")
        self.assertEqual(result, "FOO")

    def test_find_zone_id_for_domain_no_results(self):
        self.client.r53.get_paginator = mock.MagicMock()
        self.client.r53.get_paginator().paginate.return_value = []

        self.assertRaises(errors.PluginError,
                          self.client._find_zone_id_for_domain,
                          "foo.example.com")

    def test_find_zone_id_for_domain_no_correct_results(self):
        self.client.r53.get_paginator = mock.MagicMock()
        self.client.r53.get_paginator().paginate.return_value = [
            {
                "HostedZones": [
                    self.PRIVATE_ZONE,
                    self.EXAMPLE_NET_ZONE,
                ]
            },
        ]

        self.assertRaises(errors.PluginError,
                          self.client._find_zone_id_for_domain,
                          "foo.example.com")

    def test_change_txt_record(self):
        self.client._find_zone_id_for_domain = mock.MagicMock()
        self.client.r53.change_resource_record_sets = mock.MagicMock(
            return_value={"ChangeInfo": {"Id": 1}})

        self.client._change_txt_record("FOO", DOMAIN, "foo")

        self.client.r53.change_resource_record_sets.assert_called_once()

    def test_wait_for_change(self):
        self.client.r53.get_change = mock.MagicMock(
            side_effect=[{"ChangeInfo": {"Status": "PENDING"}},
                         {"ChangeInfo": {"Status": "INSYNC"}}])

        self.client._wait_for_change(1)

        self.client.r53.get_change.assert_called()


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
