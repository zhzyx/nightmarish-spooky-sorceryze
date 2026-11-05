import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import closing

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'customizations/components/godot-host/daqian'))
import model_catalog as catalog
from model_api import result_data


class Models(unittest.TestCase):
    def test_catalog_separates_gates_scores_and_secrets(self):
        with tempfile.TemporaryDirectory() as directory, closing(catalog.database(directory)) as db:
            profile = {"name":"私有配置","protocol":"responses","model":"profile-a","endpoint":"https://example.test/v1/responses"}
            secrets = {}
            a = catalog.add(db,profile,"private-unit-value",secrets.__setitem__)
            b = catalog.add(db,dict(profile,model="profile-b"),"other-unit-value",secrets.__setitem__)
            self.assertNotIn("private-unit-value",json.dumps(catalog.profiles(db)))
            self.assertEqual(catalog.sinan_catalog(db,["image"]),[])
            catalog.record_evaluation(db,a,"image","synthetic",True,[True,False],"fixture-a")
            catalog.record_evaluation(db,b,"image","synthetic",True,[True,True],"fixture-b")
            ranked = catalog.sinan_catalog(db,["image"],"synthetic",preferred=a)
            self.assertEqual([c["id"] for c in ranked],[b,a])
            self.assertEqual(catalog.sinan_catalog(db,["image"],"live"),[])
            catalog.record_evaluation(db,b,"image","synthetic",False,[True,True],"failed")
            self.assertEqual([c["id"] for c in catalog.sinan_catalog(db,["image"],"synthetic")],[a])
            self.assertEqual(catalog.sinan_catalog(db,["text","image"],"synthetic"),[])
            self.assertNotIn(b"private-unit-value",(Path(directory)/'models.sqlite').read_bytes())

    def test_incomplete_responses(self):
        for protocol, raw in [
            ("responses",{"status":"incomplete","output":[]}),
            ("gemini-generate-content",{"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[{"text":"part"}]}}]}),
            ("anthropic-messages",{"stop_reason":"max_tokens","content":[{"type":"text","text":"part"}]}),
            ("chat-completions",{"choices":[{"finish_reason":"length","message":{"content":"part"}}]})]:
            with self.subTest(protocol=protocol), self.assertRaisesRegex(ValueError,"完整"):
                result_data(protocol,raw)


if __name__=="__main__":
    unittest.main()
