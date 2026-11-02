#!/usr/bin/env python3
"""V2 regressions: real filesystem and mocked API contract, not real WeChat acceptance."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import fixtures
import publish
from safety import local_path

HERE = Path(__file__).resolve().parent

class V2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixtures.build(str(self.root))
        self.md = self.root / 'v2.md'
        self.md.write_text('---\ntitle: 测试\ncover: images/cover.jpg\ncomposition: explainer\n---\n正文。\n\n![说明](images/fig.jpg "解释 inset")\n', encoding='utf-8')
        self.html = self.root / 'delivery' / 'body.html'
        run = subprocess.run([sys.executable, str(HERE/'render.py'), str(self.md), '-o', str(self.html)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.side = json.loads(self.html.with_suffix('.meta.json').read_text())
        self.settings = dict(title=self.side['api_title'], author=None, digest=self.side['digest'], source=None, cover=publish.resolve_cover(self.side['cover'], str(self.html)), open_comment=True, fans_only=False, submit=False)

    def flight(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return publish.preflight(str(self.html), self.settings)

    def test_integrity(self):
        self.assertEqual(self.flight(), 0)
        for file in [self.md, self.html, self.html.parent/'images/cover.jpg', self.html.parent/'images/fig.jpg', self.root/'images/fig.jpg', self.root/'images/cover.jpg']:
            old = file.read_bytes()
            file.write_bytes(old + b'x')
            self.assertEqual(self.flight(), 1, str(file))
            file.write_bytes(old)
        self.assertEqual(self.side['decision']['composition'], 'explainer')

    def test_boundaries(self):
        outside = self.root/'outside.jpg'; outside.write_bytes(b'private')
        link = self.html.parent/'link.jpg'; link.symlink_to(outside)
        for path in ('../outside.jpg', str(outside), 'link.jpg', 'C:/file.jpg', 'https://example.com/x', 'x\\y'):
            with self.assertRaises(ValueError, msg=path): local_path(path, str(self.html.parent))
            with patch.object(publish, 'upload_content_image') as upload:
                with self.assertRaises(ValueError):
                    publish.rewrite_local_images('<img src="'+path+'">', 'token', str(self.html.parent)) if not path.startswith('https:') else local_path(path, str(self.html.parent))
                upload.assert_not_called()

    def test_render_rejects_escaping_cover(self):
        self.md.write_text('---\ntitle: 测试\ncover: ../outside.jpg\n---\n正文。\n', encoding='utf-8')
        output = self.root/'bad.html'
        result = subprocess.run([sys.executable, str(HERE/'render.py'), str(self.md), '-o', str(output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_readback_blocks_submission(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(publish, 'get_stable_access_token', return_value='token'), \
             patch.object(publish, 'upload_thumb_material', return_value='thumb'), \
             patch.object(publish, 'upload_content_image', return_value='https://img.example/test'), \
             patch.object(publish, 'create_draft', return_value='existing-draft'), \
             patch.object(publish, 'read_draft', side_effect=OSError('network')), \
             patch.object(publish, 'submit_publish') as submit:
            with self.assertRaisesRegex(RuntimeError, 'existing-draft'):
                publish.publish_html_article('app', 'secret', str(self.html), self.settings['cover'], self.settings['title'], material_cache=None, do_submit=True, submit_confirm=self.settings['title'])
            submit.assert_not_called()

    def test_readback(self):
        self.assertEqual(publish.verify_draft({'news_item':[{'title':'题','content':'文','thumb_media_id':'x'}]}, '题','文','x'), [])
        self.assertEqual(publish.verify_draft({'news_item':[{'title':'错','content':'文','thumb_media_id':'x'}]}, '题','文','x'), ['title'])
        with self.assertRaises(ValueError): publish.verify_draft({}, '题','文','x')

if __name__ == '__main__': unittest.main()
