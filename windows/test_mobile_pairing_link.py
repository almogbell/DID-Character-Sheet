"""Qt-independent regression checks for temporary pairing QR link construction."""
import base64
import json
import unittest
from urllib.parse import urlsplit
from mobile_pairing_link import make_pairing_landing_url


class PairingLinkTests(unittest.TestCase):
    def setUp(self):
        self.payload = dict(type='did_pairing', pairing_token='temp.secret.token', host='192.168.1.10', port=8765, expires_at=9999999999)

    def test_token_only_in_fragment(self):
        url = make_pairing_landing_url(self.payload, 'https://example.org/pair/')
        parts = urlsplit(url)
        self.assertEqual(parts.path, '/pair/')
        self.assertFalse(parts.query)
        self.assertNotIn('token', url.split('#')[0])
        encoded = parts.fragment.removeprefix('did=')
        decoded = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        self.assertEqual(decoded, self.payload)

    def test_insecure_hosts_rejected(self):
        for host in ('http://example.com/pair/', 'javascript:alert(1)', 'https://user:pass@example.com/pair/', 'https://example.com/?id=1'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                make_pairing_landing_url(self.payload, host)

    def test_cannot_encode_permanent_credential_only(self):
        with self.assertRaises(ValueError):
            make_pairing_landing_url(dict(device_token='permanent'), 'https://example.com/')

if __name__ == '__main__':
    unittest.main()
