import unittest
import u1_entry_install as entry

class EntryTests(unittest.TestCase):
    def test_root_only_and_idempotent(self):
        site = 'server {\n    location / {\n try_files $uri /index.html; }\n    location /websocket { proxy_pass http://apiserver/websocket; }\n}\nserver {\n listen 8081;\n    location / { return 404; }\n}'
        result = entry.config(site)
        self.assertEqual(entry.config(result),result)
        self.assertIn('location = / {',result)
        self.assertIn('/u1-filaments-ui/$is_args$args#/u1-filaments',result)
        self.assertIn('location /websocket { proxy_pass http://apiserver/websocket; }',result)
        self.assertIn('location / { return 404; }',result)
    def test_unknown_route_is_not_overwritten(self):
        for existing in ('location = / {', 'location = /sw.js {', 'location = /u1-stock-sw.js {'):
            with self.assertRaises(ValueError): entry.config(existing+' }\n    location / { }')
    def test_unknown_structure_is_not_overwritten(self):
        for value in ('', entry.BEGIN, '    location / { }\n    location / { }'):
            with self.assertRaises(ValueError): entry.config(value)

if __name__ == '__main__': unittest.main()
