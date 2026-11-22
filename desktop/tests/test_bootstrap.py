"""Exercise the downloaded-code boundary without contacting any device."""
import hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bootstrap import CODE

class Bootstrap(unittest.TestCase):
    def run_bootstrap(self,version='v0.1.1-beta.3',bad_hash=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cfg=root/'printer.cfg';cfg.write_text('fixture')
            dest=root/'install.sh';calls=[]
            data=('#!/bin/sh\nVERSION='+version+'\n').encode()
            def read(request,timeout):
                url=request.full_url;calls.append(url)
                self.assertIn('?check=',url)
                self.assertEqual(request.get_header('Cache-control'),'no-cache')
                if '/releases/latest?' in url:return io.BytesIO(json.dumps({'tag_name':'v0.1.1-beta.3','draft':False}).encode())
                if '/SHA256SUMS?' in url:return io.BytesIO(((('0'*64) if bad_hash else hashlib.sha256(data).hexdigest())+'  install.sh\n').encode())
                self.assertIn('/releases/download/v0.1.1-beta.3/install.sh?',url)
                return io.BytesIO(data)
            code=CODE.replace('/oem/printer_data/config/printer.cfg',cfg.as_posix()).replace('/userdata/u1-companion-install.sh',dest.as_posix())
            with patch('os.geteuid',return_value=0,create=True),patch('platform.machine',return_value='aarch64'),patch('urllib.request.OpenerDirector.open',side_effect=read):
                exec(code,{})
            self.assertEqual(dest.read_bytes(),data)
            self.assertFalse(any('raw.githubusercontent' in u for u in calls))
    def test_latest_published_release_used_instead_of_cached_main(self):self.run_bootstrap()
    def test_tampered_bootstrap_rejected(self):
        with self.assertRaisesRegex(SystemExit,'checksum'):self.run_bootstrap(bad_hash=True)
    def test_mismatched_version_rejected(self):
        with self.assertRaisesRegex(SystemExit,'version differs'):self.run_bootstrap(version='v0.1.1-beta.2')

if __name__=='__main__':unittest.main()
