import unittest,tempfile,io
from unittest.mock import patch,MagicMock
from u1_ai.codex_account import Codex
from u1_ai.openai_client import OpenAIError
class Tests(unittest.TestCase):
 def test_rejects_config_fallback_to_shell_enabled(self):
  with tempfile.TemporaryDirectory() as root:
   c=Codex(root);p=MagicMock();p.poll.return_value=None;p.stdout=[];p.stderr=[];p.stdin=io.StringIO()
   with patch('u1_ai.codex_account.subprocess.Popen',return_value=p),patch.object(c,'rpc',side_effect=[{}, {'config':{'features':{'shell_tool':True,'apps':False,'plugins':False}}}]):
    with self.assertRaises(OpenAIError):c.start()
    p.terminate.assert_called_once()
 def test_accepts_only_confirmed_disabled_tools(self):
  with tempfile.TemporaryDirectory() as root:
   c=Codex(root);p=MagicMock();p.poll.return_value=None;p.stdout=[];p.stderr=[];p.stdin=io.StringIO()
   with patch('u1_ai.codex_account.subprocess.Popen',return_value=p),patch.object(c,'rpc',side_effect=[{}, {'config':{'features':{'shell_tool':False,'apps':False,'plugins':False}}}]):
    c.start();p.terminate.assert_not_called()
    self.assertNotIn('model_providers.openai',(c.root/'codex-home/config.toml').read_text())
unittest.main()
