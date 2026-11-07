import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign_link_guard import verify_character_link, clear_confirmed_removed_link

class FakeClient:
    user_id='player1'
    def __init__(self,rows):
        self.link={'campaign_id':'camp1','campaign_character_id':'link1'}
        self.rows=rows
        self.calls=[]
    def get_character_link(self,char):return self.link
    def unlink_local_character(self,char):self.link=None
    def _request_json(self, method, path, query):
        self.calls.append((method,path,query))
        if isinstance(self.rows,Exception):raise self.rows
        return self.rows

class LinkTests(unittest.TestCase):
    def test_removed_link_is_confirmed_remotely_before_clearing(self):
        c=FakeClient([{'id':'link1','active':False}])
        check=verify_character_link(c,'char1','camp1')
        self.assertEqual(check.status,'removed')
        self.assertTrue(clear_confirmed_removed_link(c,'char1',check))
        self.assertIsNone(c.link)
        self.assertEqual(c.calls[0][2]['id'],'eq.link1')

    def test_no_clear_while_offline(self):
        c=FakeClient(TimeoutError('wifi unavailable'))
        check=verify_character_link(c,'char1','camp1')
        self.assertEqual(check.status,'offline')
        self.assertFalse(clear_confirmed_removed_link(c,'char1',check))
        self.assertIsNotNone(c.link)

    def test_no_clear_of_active_row(self):
        c=FakeClient([{'id':'link1','active':True}])
        check=verify_character_link(c,'char1','camp1')
        self.assertEqual(check.status,'active')
        self.assertFalse(clear_confirmed_removed_link(c,'char1',check))

    def test_local_link_replaced_during_request(self):
        c=FakeClient([])
        check=verify_character_link(c,'char1','camp1')
        c.link={'campaign_id':'camp1','campaign_character_id':'newlink'}
        self.assertFalse(clear_confirmed_removed_link(c,'char1',check))
        self.assertIsNotNone(c.link)

    def test_other_campaign_not_queried(self):
        c=FakeClient([])
        check=verify_character_link(c,'char1','camp2')
        self.assertEqual(check.status,'unlinked')
        self.assertEqual(c.calls,[])

if __name__=='__main__':unittest.main()
