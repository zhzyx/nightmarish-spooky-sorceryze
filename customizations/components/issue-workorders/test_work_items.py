import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("work_items", Path(__file__).with_name("work_items.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkItemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.github').mkdir()
        (self.root / 'design-docs').mkdir()
        (self.root / 'work-items.json').write_text('{"repository":"test/repo"}')
        (self.root / '.github/labels.json').write_text('[{"name":"type:design","color":"123456","description":"design"}]')
        (self.root / 'design-docs/req.md').write_text('# Actual requirement\n')

    def create(self, apply=False, document='design-docs/req.md'):
        return module.issue(self.root, document, 'Title', 'design', 'req-1', apply)

    def test_preview_has_no_network_side_effects(self):
        with patch.object(module, 'gh') as gh:
            self.assertEqual(self.create()['state'], 'planned')
            module.labels(self.root)
        gh.assert_not_called()

    def test_document_cannot_escape_design_directory(self):
        with self.assertRaises(ValueError):
            self.create(document='../outside.md')

    def test_unknown_category_rejected(self):
        with self.assertRaises(ValueError):
            module.issue(self.root, 'design-docs/req.md', 'Title', 'unknown', 'req-1')

    def test_existing_closed_issue_reused(self):
        response = [[{'state':'closed','body':'<!-- olympus-request:req-1 -->','html_url':'https://github.com/test/repo/issues/1'}]]
        with patch.object(module,'gh',return_value=json.dumps(response)) as gh:
            self.assertEqual(self.create(True)['state'],'existing')
        self.assertEqual(gh.call_count,1)

    def test_duplicate_remote_identity_rejected(self):
        response = [[{'body':'<!-- olympus-request:req-1 -->'}]*2]
        with patch.object(module,'gh',return_value=json.dumps(response)):
            with self.assertRaises(ValueError):
                self.create(True)

    def test_existing_label_not_overwritten(self):
        with patch.object(module,'gh',return_value='[[{"name":"type:design"}]]') as gh:
            module.labels(self.root,True)
        self.assertEqual(gh.call_count,1)

    def test_create_uses_exact_body_file(self):
        def fake(*args):
            if args[0]=='api':
                return '[[]]'
            self.assertEqual(args[:2],('issue','create'))
            body = Path(args[args.index('--body-file')+1]).read_text(encoding='utf-8')
            self.assertIn('<!-- olympus-request:req-1 -->',body)
            self.assertIn('# Actual requirement',body)
            return 'https://github.com/test/repo/issues/2'
        with patch.object(module,'gh',side_effect=fake):
            self.assertEqual(self.create(True)['state'],'created')

    def test_failed_validation_never_publishes_index(self):
        with patch.object(module.subprocess,'run') as run:
            run.return_value.returncode=1
            with self.assertRaises(ValueError):
                module.collect(self.root,'req-1')
        self.assertFalse((self.root/'data-collection').exists())

    def test_forms_match_label_definitions(self):
        _, labels = module.config(module.ROOT)
        forms = [json.loads((module.ROOT/'.github/ISSUE_TEMPLATE'/ (label['name'].split(':')[1]+'.yml')).read_text(encoding='utf-8')) for label in labels]
        self.assertEqual({x['name'] for x in labels},{f['labels'][0] for f in forms})
        self.assertTrue(all(len(f['labels'])==1 for f in forms))


if __name__=='__main__':
    unittest.main()
