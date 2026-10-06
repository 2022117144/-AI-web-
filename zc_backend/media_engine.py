"""Verified project media, narration timing and cancellable local FFmpeg assembly."""
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).parent / 'data' / 'project_content'
_locks = {}
_locks_guard = threading.Lock()

class Cancelled(RuntimeError):
    pass

def check(cancel=None):
    if cancel and cancel():
        raise Cancelled('用户取消执行')

def project_dir(pid):
    if not pid or not re.fullmatch(r'[\w-]+', pid):
        raise ValueError('无效项目 ID')
    path = (ROOT / pid).resolve()
    if ROOT.resolve() not in path.parents:
        raise ValueError('项目路径无效')
    return path

def project_lock(pid):
    with _locks_guard:
        return _locks.setdefault(pid, threading.Lock())

def read(path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding='utf-8'))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + str(threading.get_ident()) + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def process(args, cancel=None, timeout=600, cwd=None, input_text=None):
    check(cancel)
    # Files avoid pipe-buffer deadlocks while polling a long-running encoder.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([str(a) for a in args], cwd=cwd, stdout=out, stderr=err,
                                stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            if input_text is not None:
                proc.stdin.write(input_text.encode('utf-8'))
                proc.stdin.close()
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                check(cancel)
                if time.monotonic() > deadline:
                    raise TimeoutError('处理超时，请重试或增加超时配置')
                time.sleep(.1)
            out.seek(0); err.seek(0)
            stdout = out.read().decode('utf-8', errors='replace')
            stderr = err.read().decode('utf-8', errors='replace')
            if proc.returncode:
                raise RuntimeError(stderr[-2400:] or stdout[-1200:] or '媒体处理失败')
            return stdout
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

def probe(path, kind=None, cancel=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('素材缺失或为空: ' + path.name)
    info = json.loads(process(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                              '-of', 'json', path], cancel, timeout=30))
    duration = float(info.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('素材时长无效: ' + path.name)
    streams = info.get('streams', [])
    if kind and not any(s.get('codec_type') == kind for s in streams):
        raise ValueError('素材缺少' + kind + '流: ' + path.name)
    return duration, streams

def valid(path, kind):
    try:
        probe(path, kind)
        return True
    except (OSError, ValueError, RuntimeError, TimeoutError):
        return False

def file_url(pid, path):
    from urllib.parse import quote
    rel = Path(path).resolve().relative_to(project_dir(pid))
    return '/api/project-files/' + quote(pid) + '/' + '/'.join(quote(p) for p in rel.parts)

def local_path(pid, value):
    base = project_dir(pid)
    text = unquote(str(value or '')).replace('\\', '/')
    prefix = '/api/project-files/' + pid + '/'
    if text.startswith(prefix):
        path = base / text[len(prefix):]
    elif Path(text).is_absolute():
        path = Path(text)
    else:
        if text.startswith(pid + '/'):
            text = text[len(pid) + 1:]
        path = base / text
    path = path.resolve()
    if base not in path.parents or not path.is_file():
        raise ValueError('项目素材路径无效或不存在')
    return path

def materialize(pid, value, destination, cancel=None):
    if not str(value).startswith(('https://', 'http://')):
        return local_path(pid, value)
    import httpx
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + '.download')
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            with client.stream('GET', value) as response:
                response.raise_for_status()
                with tmp.open('wb') as f:
                    for chunk in response.iter_bytes():
                        check(cancel); f.write(chunk)
        check(cancel)
        os.replace(tmp, destination)
        return destination
    finally:
        tmp.unlink(missing_ok=True)

def content(pid):
    base = project_dir(pid)
    script = base / '文案/script.txt'
    return {'script_text': script.read_text(encoding='utf-8') if script.exists() else '',
            'shots': read(base / '视频提示词/shots.json', []),
            'shot_data': read(base / '视频提示词/shot_data.json', {})}

def texts(shots):
    result = [str(s.get('voiceover') or s.get('script_text') or '').strip() for s in shots]
    if not result or any(not t for t in result):
        raise ValueError('每个分镜都需要旁白文本，请先补全分镜剧本再配音')
    return result

def audio_manifest(pid, shots):
    doc = read(project_dir(pid) / '音频/narration.json', {})
    entries = doc.get('entries', {})
    result = []
    for i, text in enumerate(texts(shots)):
        entry = entries.get(str(i), {})
        if entry.get('text') != text:
            raise ValueError('分镜配音缺失或已过期: ' + str(i + 1))
        path = local_path(pid, entry.get('path', ''))
        duration, _ = probe(path, 'audio')
        cues = entry.get('cues', [])
        if not cues or any(not c.get('text') or not 0 <= float(c['start']) < float(c['end']) <= duration + .1 for c in cues):
            raise ValueError('分镜字幕时间戳缺失或无效: ' + str(i + 1))
        result.append({**entry, 'path': str(path), 'duration': duration})
    return result

def timecode(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'

def make_cues(text, duration, events):
    # Word boundaries come from actual TTS audio; combine them into readable cues.
    cues, group = [], []
    for event in events:
        group.append(event)
        if len(''.join(e['text'] for e in group)) >= 18 or re.search(r'[。！？!?]$', event['text']):
            cues.append(group); group = []
    if group:
        cues.append(group)
    if not cues:
        raise ValueError('配音未提供字幕时间戳，无法验证字幕对齐')
    result = []
    for group in cues:
        start = max(0, float(group[0]['offset']) / 1e7)
        end = min(duration, (float(group[-1]['offset']) + float(group[-1]['duration'])) / 1e7)
        if end <= start:
            continue
        words = [e['text'] for e in group]
        caption = ''.join(words) if re.search(r'[\u4e00-\u9fff]', text) else ' '.join(words)
        result.append({'start': start, 'end': end, 'text': caption})
    if not result:
        raise ValueError('字幕时间戳无效')
    return result

def narrate(pid, shots, voice='zh-CN-XiaoxiaoNeural', cancel=None, only=None):
    base = project_dir(pid)
    lines = texts(shots) if only is None else [str(s.get('voiceover') or s.get('script_text') or '').strip() for s in shots]
    if only is not None and not lines[only]:
        raise ValueError('请先填写该分镜的旁白文本')
    manifest_path = base / '音频/narration.json'
    doc = read(manifest_path, {'entries': {}})
    entries = doc.setdefault('entries', {})
    for i, text in enumerate(lines):
        if only is not None and i != only:
            continue
        check(cancel)
        previous = entries.get(str(i), {})
        if previous.get('text') == text and previous.get('voice') == voice:
            try:
                if valid(local_path(pid, previous['path']), 'audio') and previous.get('cues'):
                    continue
            except (ValueError, KeyError):
                pass
        folder = base / '音频'; folder.mkdir(parents=True, exist_ok=True)
        # Content-addressed audio keeps old manifests usable if generation fails.
        path = folder / f'shot_{i}_{digest([text, voice])[:12]}.mp3'
        wrapper = Path(__file__).parent / '_edge_tts_wrapper.py'
        output = process([sys.executable, wrapper, '-', voice, path], cancel,
                         timeout=max(120, min(900, len(text) * 2)), input_text=text)
        response = json.loads(output)
        if not response.get('success'):
            raise RuntimeError(response.get('error', '配音生成失败'))
        duration, _ = probe(path, 'audio', cancel)
        entries[str(i)] = {'text': text, 'voice': voice, 'path': str(path),
                           'duration': duration, 'url': file_url(pid, path),
                           'cues': make_cues(text, duration, response.get('events', []))}
        write(manifest_path, doc)
    try:
        complete = audio_manifest(pid, shots)
    except (ValueError, OSError, RuntimeError, TimeoutError):
        complete = []
    if complete:
        offset = 0.; cues = []
        for i, entry in enumerate(complete):
            cues.extend({**c, 'start': c['start'] + offset, 'end': c['end'] + offset} for c in entry['cues'])
            duration = entry['duration'] + .15
            try:
                clip = videos(pid, [shots[i]], start_index=i)[0]
                duration = max(duration, probe(clip, 'video')[0])
            except (ValueError, OSError, RuntimeError, TimeoutError):
                pass
            offset += duration
        write(base / '视频提示词/srt.json', cues)
    return doc

def videos(pid, shots, shot_data=None, cancel=None, allow_download=False, start_index=0):
    base = project_dir(pid)
    data = shot_data if shot_data is not None else content(pid)['shot_data']
    paths = []
    for i, _ in enumerate(shots, start_index):
        check(cancel)
        entry = data.get(str(i), {})
        value = entry.get('video') or entry.get('videoUrl') or entry.get('videoLocal')
        path = None
        if value:
            if str(value).startswith(('http://', 'https://')) and not allow_download:
                raise ValueError(f'分镜 {i + 1} 视频尚未下载到项目')
            path = materialize(pid, value, base / '视频' / f'shot_{i}.mp4', cancel)
            if str(value).startswith(('http://', 'https://')):
                data.setdefault(str(i), {}).update({'video': file_url(pid, path), 'videoLocal': str(path)})
                write(base / '视频提示词/shot_data.json', data)
        else:
            path = next((base / '视频' / f'shot_{i}{ext}' for ext in ('.mp4', '.webm', '.mov')
                         if (base / '视频' / f'shot_{i}{ext}').exists()), None)
        if path is None:
            raise ValueError(f'分镜 {i + 1} 缺少视频')
        probe(path, 'video', cancel)
        paths.append(path)
    if not paths:
        raise ValueError('没有可合成的分镜')
    return paths

def image_valid(pid, value):
    try:
        path = local_path(pid, value)
        return path.stat().st_size > 0 and any(s.get('codec_type') == 'video' for s in json.loads(
            process(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], timeout=20)).get('streams', []))
    except (ValueError, OSError, RuntimeError, TimeoutError):
        return False

def image_value(pid, data, i, frame):
    entry = data.get(str(i), {})
    key = frame + 'Frame'
    value = entry.get(key) or entry.get(key + 'Local') or entry.get(key + 'Url') or entry.get(key + 'Uploaded')
    if not value:
        base = project_dir(pid) / '图片'
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            candidate = base / f'shot_{i}_{frame}_frame{ext}'
            if candidate.exists():
                return str(candidate)
    return value

def media_signature(paths):
    return [[str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns] for p in paths]

def export_source(pid):
    doc = content(pid)
    shots = doc['shots']
    audio = audio_manifest(pid, shots)
    clips = videos(pid, shots)
    return digest([shots, doc['script_text'], media_signature(clips),
                   media_signature([Path(a['path']) for a in audio]),
                   [a['cues'] for a in audio]])

def final_valid(pid):
    base = project_dir(pid)
    result = read(base / '视频/export.json', {})
    try:
        if result.get('source') != export_source(pid):
            return False
        path = base / '视频/merged_video.mp4'
        duration, streams = probe(path, 'video')
        if not any(s.get('codec_type') == 'audio' for s in streams):
            return False
        if abs(duration - float(result['duration'])) > .3:
            return False
        if result.get('bgm_path') and result.get('bgm_signature') != media_signature([Path(result['bgm_path'])]):
            return False
        return result.get('file_signature') == media_signature([path])
    except (ValueError, OSError, KeyError, RuntimeError, TimeoutError):
        return False

def status(pid):
    doc = content(pid); shots = doc['shots']; data = doc['shot_data']
    steps = [bool(doc['script_text'].strip()), False, False, False, False, False]
    errors = {}
    if shots:
        try:
            audio_manifest(pid, shots); steps[1] = True
        except (ValueError, RuntimeError, OSError, TimeoutError) as e:
            errors['audio'] = str(e)
        steps[2] = all(image_valid(pid, image_value(pid, data, i, 'last')) and
                       image_valid(pid, image_value(pid, data, i - 1, 'last') if i else image_value(pid, data, i, 'first'))
                       for i in range(len(shots)))
        try:
            # Status never downloads remote URLs or treats a filename count as validation.
            local_data = {k: {**v, 'video': v.get('videoLocal') or v.get('video') or v.get('videoUrl')} for k, v in data.items()}
            if any(str(v.get('video', '')).startswith(('http://', 'https://')) for v in local_data.values()):
                raise ValueError('视频尚未下载到项目')
            videos(pid, shots, local_data); steps[3] = True
        except (ValueError, OSError, RuntimeError, TimeoutError) as e:
            errors['video'] = str(e)
        try:
            steps[4] = final_valid(pid); steps[5] = steps[4]
        except (ValueError, OSError, RuntimeError, TimeoutError):
            pass
    return {'project_id': pid, 'steps': steps, 'errors': errors,
            'final_url': file_url(pid, project_dir(pid) / '视频/merged_video.mp4') if steps[5] else ''}

def assemble(pid, options=None, cancel=None):
    options = options or {}
    base = project_dir(pid)
    doc = content(pid); shots = doc['shots']
    narration = audio_manifest(pid, shots)
    clips = videos(pid, shots, cancel=cancel, allow_download=True)
    source = export_source(pid)
    aspect = options.get('ratio', '16:9')
    width, height = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080)}[aspect]
    if options.get('test_size'):
        width, height = options['test_size']
    fps = 24
    bgm = local_path(pid, options['bgm_path']) if options.get('bgm_path') else None
    if bgm:
        probe(bgm, 'audio', cancel)
    music_volume = float(options.get('music_volume', .18))
    if not 0 <= music_volume <= 1:
        raise ValueError('背景音乐音量必须在 0 到 1 之间')
    base.joinpath('视频').mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='merge_', dir=base) as workdir:
        work = Path(workdir); segments = []; cues = []; offset = 0.
        for i, (clip, audio) in enumerate(zip(clips, narration)):
            check(cancel)
            clip_duration, _ = probe(clip, 'video', cancel)
            target = max(clip_duration, audio['duration'] + .15)
            # Hold the final frame; never slow a speaking face or its mouth movements.
            padding = max(0, target - clip_duration) + 1 / fps
            segment = work / f'seg_{i:04}.mp4'
            vf = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={padding:.6f}'
            process(['ffmpeg', '-y', '-v', 'error', '-i', clip, '-i', audio['path'], '-map', '0:v:0', '-map', '1:a:0',
                     '-vf', vf, '-af', f'apad,atrim=duration={target:.6f}', '-t', f'{target:.6f}',
                     '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                     '-c:a', 'aac', '-ar', '48000', '-ac', '2', segment], cancel)
            duration, _ = probe(segment, 'video', cancel)
            for cue in audio['cues']:
                cues.append({**cue, 'start': cue['start'] + offset, 'end': cue['end'] + offset})
            offset += duration; segments.append(segment)
        (work / 'segments.txt').write_text(''.join(f"file '{p.name}'\n" for p in segments), encoding='utf-8')
        srt_text = '\n\n'.join(f"{i+1}\n{timecode(c['start'])} --> {timecode(c['end'])}\n{c['text']}" for i,c in enumerate(cues)) + '\n'
        (work / 'captions.srt').write_text(srt_text, encoding='utf-8')
        process(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i','segments.txt','-c','copy','body.mp4'],cancel,cwd=work)
        command = ['ffmpeg','-y','-v','error','-i','body.mp4']
        if bgm:
            command += ['-stream_loop','-1','-i',bgm]
            fc = f'[0:a]asplit=2[vo][sc];[1:a]volume={music_volume},atrim=duration={offset},afade=t=out:st={max(0,offset-1)}:d=1[bg];[bg][sc]sidechaincompress=threshold=0.02:ratio=8:attack=10:release=300[duck];[vo][duck]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]'
            command += ['-filter_complex',fc,'-map','0:v:0','-map','[a]']
        else:
            command += ['-map','0:v:0','-map','0:a:0','-af','alimiter=limit=0.95']
        # libass uses a 288-high virtual canvas for SRT, not output pixels.
        command += ['-vf', "subtitles=filename=captions.srt:force_style='FontName=Microsoft YaHei,FontSize=12,Outline=1,MarginV=12'",
                    '-t',str(offset),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
                    '-c:a','aac','-ar','48000','-movflags','+faststart','final.mp4']
        process(command,cancel,cwd=work)
        duration, streams = probe(work / 'final.mp4','video',cancel)
        if not any(s.get('codec_type')=='audio' for s in streams) or abs(duration-offset) > .3:
            raise ValueError('成片音轨或时长验证失败')
        check(cancel)
        if source != export_source(pid):
            raise ValueError('项目素材在合成期间发生变化，请重试')
        dest=base/'视频/merged_video.mp4'
        os.replace(work/'final.mp4',dest)
        shutil.copyfile(work/'captions.srt',base/'视频/captions.srt')
        result={'merged_video_path':str(dest),'final_url':file_url(pid,dest),'duration':duration,
                'source':source,'file_signature':media_signature([dest]),
                'bgm_path':str(bgm) if bgm else '', 'bgm_signature':media_signature([bgm]) if bgm else [],
                'options':options}
        write(base/'视频/export.json',result)
        write(base/'视频提示词/srt.json',cues)
        return result

def await_cancel(coroutine, cancel=None):
    async def wait():
        task = asyncio.create_task(coroutine)
        try:
            while not task.done():
                check(cancel)
                await asyncio.sleep(.1)
            return await task
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    return asyncio.run(wait())

def execute(run, config):
    """One authoritative task per project. Reuse only verified project artifacts."""
    import pipeline as pl
    import server as api
    pid=run.project_id; cancel=lambda:run.cancel_requested
    action=config.get('action','full'); base=project_dir(pid)
    def stage(i, operation):
        check(cancel); run.current_step=i; run.steps[i]['status']='running'; pl.save_run(run)
        output=operation() or {}; check(cancel)
        run.steps[i]['output']=output; run.steps[i]['status']='completed'; pl.save_run(run)
        return output
    def skip(i):
        run.steps[i]['status']='skipped'; pl.save_run(run)
    doc=content(pid)
    if not doc['script_text'].strip() and config.get('script',{}).get('script_text'):
        path=base/'文案/script.txt'; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(config['script']['script_text'],encoding='utf-8'); doc=content(pid)
    def script():
        if not doc['script_text'].strip():
            raise ValueError('请先输入并保存文案')
        return {'script_text':doc['script_text']}
    if action == 'full': stage(0,script)
    else: skip(0)
    def speech():
        nonlocal doc
        if not doc['shots']:
            if action!='full':
                raise ValueError('请先分析文案生成分镜')
            tid='media_'+run.run_id
            with api._task_lock:
                api._task_store[tid]={'status':'running','result':None}
            worker=threading.Thread(target=api._run_llm_task,args=(tid,'analyze',{'topic':doc['script_text'],'project_id':pid,
                        'style_anchor':config.get('storyboard_with_audio',{}).get('style_anchor','')}),daemon=True)
            worker.start(); deadline=time.monotonic()+300
            while worker.is_alive():
                check(cancel)
                if time.monotonic()>deadline: raise TimeoutError('分镜分析超时')
                time.sleep(.2)
            task=api._task_store.pop(tid)
            result=task.get('result') or {}
            if task['status']!='completed' or not result.get('shots'):
                raise ValueError(task.get('error') or '分镜分析失败，未生成分镜')
            if content(pid)['script_text'] != doc['script_text']:
                raise ValueError('文案在分析期间发生变化，请重试')
            write(base/'视频提示词/shots.json',result['shots']); doc=content(pid)
        only=config.get('shot_index') if action=='voice' else None
        if only is not None and (not isinstance(only,int) or not 0<=only<len(doc['shots'])):
            raise ValueError('分镜序号无效')
        voice=config.get('storyboard_with_audio',{}).get('voice_name','zh-CN-XiaoxiaoNeural')
        narrate(pid,doc['shots'],voice,cancel,only=only)
        if action=='voice' and only is not None:
            return {'message':f'分镜 {only+1} 配音完成'}
        return {'shots':doc['shots'],'shot_count':len(doc['shots']),'message':'分镜旁白和字幕时间戳已验证'}
    if action!='export': stage(1,speech)
    else:
        skip(1); audio_manifest(pid,doc['shots'])
    if action=='voice':
        for i in range(2,6): skip(i)
        return
    def images():
        data=content(pid)['shot_data']
        for i,shot in enumerate(doc['shots']):
            for frame in (('first','last') if i==0 else ('last',)):
                check(cancel); value=image_value(pid,data,i,frame)
                if value and str(value).startswith('data:'):
                    path = api._save_data_url_to_project(pid, '图片', value, f'shot_{i}_{frame}_frame')
                    value = file_url(pid, path)
                    data.setdefault(str(i), {})[frame+'Frame'] = value
                    write(base/'视频提示词/shot_data.json', data)
                if value and image_valid(pid,value): continue
                prompt=shot.get(frame+'_frame_prompt') or shot.get('enhanced_prompt') or shot.get('prompt') or shot.get('scene')
                if not prompt: raise ValueError(f'分镜 {i+1} 缺少图片提示词')
                result=await_cancel(api.generate_frame(api.FrameGenRequest(prompt=prompt,project_id=pid,shot_idx=i,mode=frame+'_frame',
                                  aspect_ratio=config.get('photogpt_images',{}).get('aspect_ratio','16:9'))),cancel)
                if not result or not result.get('success') or not result.get('image_url'):
                    raise ValueError((result or {}).get('error','图片生成失败'))
                if not image_valid(pid, result['image_url']):
                    raise ValueError(f'分镜 {i+1} 图片为空或无法读取')
                data.setdefault(str(i),{})[frame+'Frame']=result['image_url']
                write(base/'视频提示词/shot_data.json',data)
        return {'message':'每个镜头的首尾帧已验证'}
    if action=='full': stage(2,images)
    else: skip(2)
    def generate_videos():
        data=content(pid)['shot_data']; options=config.get('insmind_video',{})
        for i,shot in enumerate(doc['shots']):
            check(cancel)
            try:
                videos(pid,[shot],data,cancel,allow_download=True,start_index=i)
                continue
            except (ValueError,KeyError,RuntimeError,OSError,TimeoutError): pass
            first=image_value(pid,data,i-1,'last') if i else image_value(pid,data,i,'first')
            last=image_value(pid,data,i,'last')
            prompt=shot.get('video_prompt') or shot.get('enhanced_prompt') or shot.get('prompt') or shot.get('last_frame_prompt')
            if not prompt: raise ValueError(f'分镜 {i+1} 缺少视频提示词')
            result=await_cancel(api.generate_video(api.VideoGenRequest(prompt=prompt,first_frame=first or '',last_frame=last or '',
                    project_id=pid,shot_idx=i,model=options.get('model','Seedance-2.0-Mini'),ratio=options.get('ratio','16:9'),
                    resolution=options.get('resolution','360p'),duration=int(shot.get('duration',5)))),cancel)
            if not result or not result.get('success') or not result.get('video_url'):
                raise ValueError((result or {}).get('error','视频生成失败'))
            data.setdefault(str(i),{})['video']=result['video_url']
            if result.get('local_path'): data[str(i)]['videoLocal']=result['local_path']
            write(base/'视频提示词/shot_data.json',data)
        paths=videos(pid,doc['shots'],data,cancel)
        return {'video_paths':[str(p) for p in paths],'shot_count':len(paths),'success_count':len(paths)}
    if action=='full': stage(3,generate_videos)
    else:
        skip(3); videos(pid,doc['shots'],cancel=cancel)
    result=stage(4,lambda:assemble(pid,config.get('ffmpeg_merge',{}),cancel))
    stage(5,lambda:result if final_valid(pid) else (_ for _ in ()).throw(ValueError('导出验证失败')))
