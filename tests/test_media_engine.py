"""Offline integration tests: real FFmpeg, isolated projects, no model charges."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'zc_backend'))
import media_engine as media
import pipeline
import server

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wx-media-tests-')
        self.base = Path(self.temp.name)
        self.root_patch = patch.object(media, 'ROOT', self.base)
        self.root_patch.start()
        self.runs_patch = patch.object(pipeline, 'RUNS_FILE', self.base / 'runs.json')
        self.runs_patch.start()
        self.state_patch = patch.object(pipeline, '_runs', {})
        self.state_patch.start()
        self.pid = 'test_project'; self.folder = media.project_dir(self.pid)
        self.folder.mkdir()
    def tearDown(self):
        self.state_patch.stop(); self.runs_patch.stop(); self.root_patch.stop(); self.temp.cleanup()
    def ff(self, args):
        media.process(['ffmpeg', '-y', '-v', 'error', *args])
    def fixture(self):
        shots = [{'voiceover': '你好，第一镜头。', 'prompt': 'first'}, {'voiceover': '第二镜头。', 'prompt': 'second'}]
        media.write(self.folder / '视频提示词/shots.json', shots)
        (self.folder / '文案').mkdir()
        (self.folder / '文案/script.txt').write_text('你好，第一镜头。第二镜头。', encoding='utf-8')
        (self.folder / '视频').mkdir(); (self.folder / '音频').mkdir()
        entries = {}
        for i, (size, fps, length) in enumerate([('96x64', 15, .4), ('64x96', 30, .6)]):
            clip = self.folder / f'视频/shot_{i}.mp4'
            self.ff(['-f','lavfi','-i',f'color=c={"navy" if i==0 else "maroon"}:s={size}:r={fps}',
                     '-t',str(length),'-c:v','libx264','-pix_fmt','yuv420p',str(clip)])
            audio = self.folder / f'音频/shot_{i}.mp3'
            self.ff(['-f','lavfi','-i',f'sine=frequency={440+i*220}:sample_rate=24000','-t',str(.9 if i==0 else .45),
                     '-c:a','libmp3lame','-b:a','48k',str(audio)])
            duration,_ = media.probe(audio,'audio')
            entries[str(i)] = {'text':shots[i]['voiceover'], 'voice':'zh-CN-XiaoxiaoNeural', 'path':str(audio),
                               'duration':duration,'url':media.file_url(self.pid,audio),
                               'cues':[{'start':0.,'end':duration-.05,'text':shots[i]['voiceover']}]}
        media.write(self.folder / '音频/narration.json', {'entries':entries})
        return shots
    def test_mixed_sizes_fps_long_audio_and_bgm(self):
        self.fixture()
        bgm = self.folder / '音频/bgm.mp3'
        self.ff(['-f','lavfi','-i','sine=frequency=110:sample_rate=48000','-t','0.2','-c:a','libmp3lame',str(bgm)])
        result = media.assemble(self.pid, {'test_size':[160,90],'bgm_path':str(bgm)})
        duration,streams = media.probe(result['merged_video_path'],'video')
        video = next(s for s in streams if s['codec_type']=='video')
        self.assertEqual((video['width'],video['height']),(160,90))
        self.assertTrue(any(s['codec_type']=='audio' for s in streams))
        self.assertGreater(duration,1.5)
        self.assertTrue(media.final_valid(self.pid))
        self.assertTrue(media.status(self.pid)['steps'][3])
        cues=media.read(self.folder/'视频提示词/srt.json')
        self.assertGreater(cues[1]['start'],1.)
        self.assertIn('第二镜头', (self.folder/'视频/captions.srt').read_text(encoding='utf-8'))
    def test_no_bgm_and_changed_script_invalidates_export(self):
        self.fixture(); media.assemble(self.pid, {'test_size':[160,90]})
        self.assertTrue(media.final_valid(self.pid))
        (self.folder/'文案/script.txt').write_text('修改了文案',encoding='utf-8')
        self.assertFalse(media.final_valid(self.pid))
    def test_missing_video_not_masked_by_merged_output(self):
        self.fixture()
        (self.folder/'视频/shot_1.mp4').unlink()
        (self.folder/'视频/merged_video.mp4').touch()
        state=media.status(self.pid)
        self.assertFalse(state['steps'][3]); self.assertFalse(state['steps'][4]); self.assertFalse(state['steps'][5])
        with self.assertRaises(ValueError): media.assemble(self.pid)
    def test_stale_audio_cannot_export(self):
        self.fixture()
        shots=media.content(self.pid)['shots']; shots[0]['voiceover']='新的旁白'
        media.write(self.folder/'视频提示词/shots.json',shots)
        self.assertFalse(media.status(self.pid)['steps'][1])
        with self.assertRaises(ValueError): media.assemble(self.pid)
    def test_process_cancel_kills_worker(self):
        started=time.monotonic()
        with self.assertRaises(media.Cancelled):
            media.process([sys.executable,'-c','import time;time.sleep(30)'],lambda:time.monotonic()-started>.3)
        self.assertLess(time.monotonic()-started,3)
    def test_cancel_async_generation(self):
        async def job(): await asyncio.sleep(30)
        started=time.monotonic()
        with self.assertRaises(media.Cancelled): media.await_cancel(job(),lambda:time.monotonic()-started>.2)
        self.assertLess(time.monotonic()-started,2)
    def test_project_scope_and_path_traversal(self):
        self.fixture()
        with self.assertRaises(ValueError): media.project_dir('../other')
        with self.assertRaises(ValueError): media.local_path(self.pid,'../outside.mp3')
    def test_failure_and_cancel_persist_real_state(self):
        self.fixture()
        run=pipeline.PipelineRun(self.pid);run.init_steps({'action':'export','ffmpeg_merge':{'test_size':[160,90]}})
        with patch.object(media,'assemble',side_effect=RuntimeError('encoder failed')):
            run.run_sync({})
        self.assertEqual(run.status,'error');self.assertEqual(run.steps[4]['status'],'error')
        run=pipeline.PipelineRun(self.pid);run.init_steps({});run.cancel_requested=True
        run.run_sync({});self.assertEqual(run.status,'cancelled')
    def test_export_run_has_real_output(self):
        self.fixture()
        run=pipeline.PipelineRun(self.pid);run.init_steps({'action':'export','ffmpeg_merge':{'test_size':[160,90]}})
        result=run.run_sync({})
        self.assertEqual(result['status'],'completed',result.get('error'))
        self.assertTrue(result['final_url']);self.assertTrue(media.final_valid(self.pid))
        self.assertEqual(result['steps'][2]['status'],'skipped')
    def test_legacy_client_cannot_forge_success(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught: server.update_pipeline_step('fake',{'status':'completed'})
        self.assertEqual(caught.exception.status_code,409)
    def test_duplicate_project_task_rejected(self):
        from fastapi import HTTPException
        run=pipeline.PipelineRun(self.pid);run.init_steps({});run.status='running'
        with patch.object(server,'PROJECTS_FILE',self.base/'projects.json'):
            media.write(self.base/'projects.json',{self.pid:{}})
            with patch.object(pipeline,'get_project_runs',return_value=[run]):
                with self.assertRaises(HTTPException) as caught:
                    server.run_pipeline(server.PipelineRunRequest(project_id=self.pid))
        self.assertEqual(caught.exception.status_code,409)

    def image_fixture(self):
        (self.folder / '图片').mkdir()
        for index, frame in [(0, 'first'), (0, 'last'), (1, 'last')]:
            self.ff(['-f','lavfi','-i','color=c=blue:s=96x64','-frames:v','1',
                     str(self.folder / f'图片/shot_{index}_{frame}_frame.png')])

    def test_full_pipeline_reuses_verified_assets(self):
        self.fixture(); self.image_fixture()
        run=pipeline.PipelineRun(self.pid);run.init_steps({'ffmpeg_merge':{'test_size':[160,90]}})
        # Offline fixture already has valid narration; paid providers must not be contacted.
        with patch.object(media,'narrate',return_value={}):
            with patch.object(server,'generate_video',side_effect=AssertionError('existing clips should be reused')):
                result=run.run_sync({})
        self.assertEqual(result['status'],'completed',result.get('error'))
        self.assertTrue(all(s['status']=='completed' for s in result['steps']))
        self.assertTrue(media.status(self.pid)['steps'][5])

    def test_voice_failure_stops_pipeline(self):
        self.fixture()
        run=pipeline.PipelineRun(self.pid);run.init_steps({})
        with patch.object(media,'narrate',side_effect=RuntimeError('TTS unavailable')):
            result=run.run_sync({})
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['steps'][1]['status'],'error')
        self.assertEqual(result['steps'][4]['status'],'pending')

    def test_restart_preserves_output_and_reports_interruption(self):
        run=pipeline.PipelineRun(self.pid);run.init_steps({'action':'voice'})
        run.status='running';run.current_step=1;pipeline.save_run(run)
        with patch.object(pipeline,'_runs',{}):
            pipeline.load_runs();loaded=pipeline.get_run(run.run_id)
            self.assertEqual(loaded.status,'error');self.assertEqual(loaded.current_step,1)
            self.assertEqual(loaded.config['action'],'voice')

    def test_all_video_failures_are_not_success(self):
        import handlers
        from types import SimpleNamespace
        fake=SimpleNamespace(post=lambda *a,**k:SimpleNamespace(status_code=500,text='unavailable'),ConnectError=ConnectionError)
        with patch.object(handlers,'httpx',fake):
            result=handlers.insmind_video_handler({}, {'shots':[{'prompt':'test'}]})
        self.assertFalse(result['success']);self.assertEqual(result['output']['success_count'],0)

    def test_voice_can_generate_single_row_with_other_empty_rows(self):
        shots=self.fixture();shots[1]['voiceover']=''
        media.write(self.folder/'视频提示词/shots.json',shots)
        # Existing voice + timestamps are valid: no regeneration necessary.
        result=media.narrate(self.pid,shots,only=0)
        self.assertIn('0',result['entries'])

    def test_background_music_upload_and_invalid_audio(self):
        from fastapi.testclient import TestClient
        self.fixture()
        with patch.object(server,'PROJECTS_FILE',self.base/'projects.json'):
            media.write(self.base/'projects.json',{self.pid:{}})
            client=TestClient(server.app)
            source=(self.folder/'音频/shot_0.mp3').read_bytes()
            result=client.post(f'/api/projects/{self.pid}/background-music',content=source)
            self.assertEqual(result.status_code,200,result.text)
            media.probe(result.json()['bgm_path'],'audio')
            self.assertTrue(result.json()['url'].startswith('/api/project-files/'+self.pid+'/'))
            self.assertEqual(client.post(f'/api/projects/{self.pid}/background-music',content=b'bad audio').status_code,400)
            self.assertEqual(client.post('/api/projects/missing/background-music',content=source).status_code,404)

    def test_video_proxy_download_and_cache_are_video(self):
        from unittest.mock import MagicMock
        client=MagicMock()
        client.__enter__.return_value=client
        client.get.return_value.status_code=200
        client.get.return_value.content=b'video fixture'
        with patch.object(server,'PROJECT_CONTENT_DIR',self.base),patch.object(server._httpx,'Client',return_value=client) as factory:
            result=server.video_proxy('https://example.invalid/sample.mp4')
            self.assertEqual(result.media_type,'video/mp4')
            self.assertEqual(result.body,b'video fixture')
            self.assertEqual(client.get.call_count,1)
            self.assertIn('proxy',factory.call_args.kwargs)
            self.assertNotIn('proxies',factory.call_args.kwargs)
            cached=server.video_proxy('https://example.invalid/sample.mp4')
            self.assertEqual(cached.media_type,'video/mp4')
            self.assertEqual(client.get.call_count,1)

    def test_voice_endpoint_persists_audio_and_true_timing(self):
        from fastapi.testclient import TestClient
        self.fixture()
        with patch.object(server,'PROJECTS_FILE',self.base/'projects.json'), patch.object(server,'PROJECT_CONTENT_DIR',self.base):
            media.write(self.base/'projects.json',{self.pid:{}})
            client=TestClient(server.app)
            response=client.post('/api/pipeline/run',json={'project_id':self.pid,'config':{'action':'voice','shot_index':0}})
            self.assertEqual(response.status_code,200,response.text)
            run_id=response.json()['run_id']
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                result=client.get('/api/pipeline/runs/'+run_id).json()
                if result['status']!='running': break
                time.sleep(.1)
            self.assertEqual(result['status'],'completed',result)
            data=client.get(f'/api/projects/{self.pid}/content').json()
            entry=data['narration']['entries']['0']
            self.assertGreater(entry['duration'],.8)
            actual,_=media.probe(entry['path'],'audio')
            self.assertAlmostEqual(entry['duration'],actual,places=3)
            self.assertTrue(entry['cues'])
            self.assertEqual(client.get(entry['url']).status_code,200)

if __name__=='__main__': unittest.main()
