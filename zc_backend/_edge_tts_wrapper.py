"""Isolated TTS worker; UTF-8 stdin and actual word-boundary timestamps."""
import asyncio, json, os, sys
from pathlib import Path
import edge_tts
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
async def main():
    text=sys.stdin.buffer.read().decode('utf-8') if sys.argv[1]=='-' else sys.argv[1]
    voice,output=sys.argv[2],Path(sys.argv[3])
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.part.mp3'); events=[]
    try:
        communicate=edge_tts.Communicate(text,voice,boundary='WordBoundary',proxy=os.environ.get('EDGE_TTS_PROXY'))
        with temporary.open('wb') as audio:
            async for chunk in communicate.stream():
                if chunk['type']=='audio': audio.write(chunk['data'])
                elif chunk['type']=='WordBoundary': events.append({k:chunk[k] for k in ('offset','duration','text')})
        if not temporary.stat().st_size or not events: raise ValueError('TTS 未生成音频或时间戳')
        os.replace(temporary,output)
        print(json.dumps({'success':True,'path':str(output),'events':events},ensure_ascii=False))
    finally: temporary.unlink(missing_ok=True)
if __name__=='__main__':
    try: asyncio.run(main())
    except Exception as error:
        print(json.dumps({'success':False,'error':str(error)},ensure_ascii=False)); sys.exit(1)
