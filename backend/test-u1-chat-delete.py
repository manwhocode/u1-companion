import tempfile, unittest, uuid
from pathlib import Path
from u1_ai.agent import Agent
from u1_ai.storage import atomic, read
class Tests(unittest.TestCase):
 def test_delete_rejects_pending_and_tombstones(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);a=Agent(None,None,root);chat=str(uuid.uuid4());action=str(uuid.uuid4())
   atomic(root/'chats'/(chat+'.json'),{'id':chat,'messages':[]})
   atomic(root/'actions'/(action+'.json'),{'id':action,'chat':chat,'state':'pending'})
   with self.assertRaises(ValueError):a.delete_chat(chat,False)
   a.busy=True
   with self.assertRaises(ValueError):a.delete_chat(chat,True)
   a.busy=False;a.delete_chat(chat,True)
   self.assertEqual(a.chats(),[])
   self.assertEqual(read(root/'actions'/(action+'.json'))['state'],'rejected')
   with self.assertRaises(ValueError):a.history(chat)
if __name__=='__main__':unittest.main()
