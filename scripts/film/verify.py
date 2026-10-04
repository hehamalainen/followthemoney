"""Check the distributable MP4s, including complete decoding and fast-start layout."""
import json, struct, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[2]
for name,size in [('wide',(1920,1080)),('vertical',(1080,1920))]:
    path=root/f'dist/media/ai-money-map-30s-{name}.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert video['codec_name']=='h264' and video['pix_fmt']=='yuv420p'
    assert (video['width'],video['height'])==size
    assert video['r_frame_rate']=='30/1' and int(video['nb_frames'])==900
    assert abs(float(probe['format']['duration'])-30)<.02
    assert audio['codec_name']=='aac' and int(audio['sample_rate'])==48000 and audio['channels']==2
    assert path.stat().st_size<25*1024**2
    atoms=[]
    with path.open('rb') as f:
        while header:=f.read(8):
            length,kind=struct.unpack('>I4s',header);head=8
            if length==1:length=struct.unpack('>Q',f.read(8))[0];head=16
            if length==0:break
            atoms.append(kind);f.seek(length-head,1)
    assert atoms.index(b'moov')<atoms.index(b'mdat'),'Video must begin without downloading the whole file'
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True)
    print(f'{name}: 30.0s, {size[0]}x{size[1]}, 900 frames, H.264/AAC stereo, fast-start, full decode passed; {path.stat().st_size/1e6:.1f} MB')
