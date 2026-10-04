#!/usr/bin/env python3
"""AI Money Map — original 30-second score; deterministic procedural synthesis.

No recordings, sample libraries, soundfonts, or existing melodies are used.
Requires Python 3 + NumPy; FFmpeg is used only for PCM delivery / analysis.
128 BPM, D minor. Sixteen bars, with picture sync points every two/four bars.
"""
from pathlib import Path
import json
import math
import subprocess
import wave
import numpy as np

OUT = Path(__file__).resolve().parent
SR = 48000
DURATION = 30.0
N = int(SR * DURATION)
BEAT = 60 / 128
BAR = BEAT * 4
RNG = np.random.default_rng(20261004)
STEMS = {name: np.zeros((N, 2), np.float64) for name in
         ['orchestra', 'ostinato', 'horns', 'bass', 'drums', 'atmosphere']}


def hz(note):
    return 440 * 2 ** ((note - 69) / 12)


def band(x, low=0, high=18000):
    """Smooth zero-phase spectral filtering; used on rendered one-shot voices."""
    n = len(x)
    bins = np.fft.rfftfreq(n, 1 / SR)
    response = 1 / np.sqrt(1 + (bins / high) ** 8)
    if low:
        response *= 1 / np.sqrt(1 + (low / np.maximum(bins, .1)) ** 8)
    return np.fft.irfft(np.fft.rfft(x) * response, n=n)


def envelope(t, gate, attack=.1, release=.3):
    a = np.sin(np.clip(t / attack, 0, 1) * np.pi / 2) ** 1.6
    r = np.exp(-np.maximum(t-gate, 0) / max(release/5.5, .002))
    tail = np.clip((gate+release-t) / .015, 0, 1)
    return a * r * tail


def add(bus, x, when, level=1, pan=0):
    start = round(when * SR)
    if x.ndim == 1:
        # Constant-power pan, kept narrower than hard L/R for mono compatibility.
        angle = (np.clip(pan, -1, 1)+1) * np.pi / 4
        x = np.column_stack([x * np.cos(angle), x * np.sin(angle)])
    a, b = max(start, 0), min(start+len(x), N)
    if b > a:
        STEMS[bus][a:b] += x[a-start:b-start] * level


def texture(note, gate, voice='strings', intensity=1, seed=0):
    """A bowed or breath-shaped ensemble, with slow uncorrelated pitch drift."""
    release = .8 if voice == 'strings' else .48
    t = np.arange(round((gate+release) * SR)) / SR
    f = hz(note)
    out = np.zeros((len(t), 2))
    rng = np.random.default_rng(7300 + seed + note * 13)
    for player, cents in enumerate([-8, -2.5, 3.5, 8]):
        vibrato = (0.0015 if voice=='strings' else .0007) * f / 5.1
        phase = 2*np.pi*(f * 2**(cents/1200)*t + vibrato*np.sin(2*np.pi*(4.8+player*.19)*t))
        phase += rng.uniform(0, 2*np.pi)
        part = np.zeros_like(t)
        cutoff = 3200 if voice=='strings' else 2600
        for h in range(1, min(23, int(16000/f))):
            fh = h*f
            if voice == 'strings':
                formant = .45 + 1.5*np.exp(-((fh-650)/420)**2) + .9*np.exp(-((fh-1650)/900)**2)
                amp = formant / h**1.14 / (1+(fh/cutoff)**4)
            else:
                formant = .55 + 1.2*np.exp(-((fh-820)/600)**2)
                amp = formant / h**.92 / (1+(fh/cutoff)**5)
            part += amp * np.sin(h*phase)
        part /= max(np.sqrt(np.mean(part**2)), 1e-8)
        pan = [-.72, .55, -.25, .83][player]
        ang = (pan+1)*np.pi/4
        out[:, 0] += part*np.cos(ang)/4
        out[:, 1] += part*np.sin(ang)/4
    attack = .32 if voice=='strings' else .065
    env = envelope(t, gate, attack, release)
    # Bow/breath dynamics keep the chord alive rather than sounding like a held organ.
    env *= .72+.18*np.sin(np.pi*np.minimum(t/max(gate,.1), 1))+.025*np.sin(2*np.pi*.65*t)
    if voice=='brass':
        env *= .82+.3*np.exp(-t/.16)
    return out * env[:, None] * intensity


def bass(note, gate, accent=1):
    t = np.arange(round((gate+.1)*SR))/SR
    f = hz(note)
    phase = 2*np.pi*f*t
    # Fundamental plus controlled low harmonics, not a high, percussive synth pluck.
    x = np.sin(phase)+.30*np.sin(2*phase)+.11*np.sin(3*phase)
    x += .30*np.sin(phase/2)
    x = np.tanh(1.12*x)
    return x*envelope(t,gate,.016,.10)*(.95-.20*np.minimum(t/.3,1))*accent


def bowed_pulse(note, duration, velocity):
    t = np.arange(round((duration+.065)*SR))/SR
    f = hz(note)
    ph = 2*np.pi*(f*t + .001*f/5*np.sin(2*np.pi*5*t))
    x = np.zeros_like(t)
    for h in range(1, min(14,int(6500/f))):
        x += np.sin(ph*h)/(h**1.15*(1+(f*h/2400)**4))
    return x*envelope(t,duration,.032,.065)*velocity


def low_drum(strength=1, length=1, tune=1):
    t=np.arange(round(length*SR))/SR
    # Three damped membrane modes and a soft felt/transient layer.
    f0=50*tune
    phase=2*np.pi*(f0*t+(.11*58*tune)*(1-np.exp(-t/.11)))
    x=np.sin(phase)*np.exp(-t/ .25)
    x+=.32*np.sin(2*np.pi*(93*tune*t+2*(1-np.exp(-t/.04))))*np.exp(-t/.17)
    x+=.16*np.sin(2*np.pi*151*tune*t)*np.exp(-t/.07)
    noise=band(RNG.normal(0,1,len(t)),100,2300)
    x+=.5*noise*np.exp(-t/.014)
    x*=np.minimum(t/.0015,1)*np.clip((length-t)/.03,0,1)
    return np.tanh(x*1.5)*strength


def war_snare(strength=1, length=.65):
    t=np.arange(round(length*SR))/SR
    n=band(RNG.normal(0,1,len(t)),550,5200)
    x=.65*n*np.exp(-t/.14)+.33*np.sin(2*np.pi*177*t)*np.exp(-t/.095)
    x+=.15*np.sin(2*np.pi*287*t)*np.exp(-t/.075)
    return np.tanh(x*1.6)*envelope(t,.42,.001,.23)*strength


def impact(when, strength=1):
    t=np.arange(round(3.2*SR))/SR
    phase=2*np.pi*(30*t+68*.12*(1-np.exp(-t/.12)))
    boom=np.sin(phase)*np.exp(-t/.7)
    body=np.sin(2*np.pi*73.416*t)*np.exp(-t/.45)*.45
    noise=band(RNG.normal(0,1,len(t)),120,4300)
    crash=noise*(.7*np.exp(-t/.06)+.25*np.exp(-t/.68))
    env=np.minimum(t/.002,1)*np.clip((3.2-t)/.07,0,1)
    add('drums',(boom+body+crash)*env,when,.68*strength)
    # Wide, dark impact reflection.
    add('atmosphere',band(crash,350,2600)*env,when+.047,.22*strength,-.75)
    add('atmosphere',band(crash,350,2200)*env,when+.079,.18*strength,.75)


def rise(start, duration, amount=.12):
    t=np.arange(round(duration*SR))/SR
    u=t/duration
    noise=band(RNG.normal(0,1,len(t)),500,5300)
    pulse=.75+.25*np.sin(2*np.pi*t/(BEAT/2))
    whoosh=noise*u**2.3*pulse
    # Continuous low rising mass; deliberately no bell-like partials.
    phase=2*np.pi*(48*t+95*t*t/(2*duration))
    whoosh+=.22*np.sin(phase)*u**1.7
    whoosh*=np.minimum((duration-t)/.012,1)
    add('atmosphere',whoosh,start,amount,-.22)
    add('atmosphere',whoosh*.8,start+.031,amount,.4)


def render_composition():
    # Intro: D pedal, breath, and restrained first impact.
    add('bass',bass(26,3.55),0,.22)
    for note,lev in [(38,.085),(45,.052),(50,.042)]:
        add('orchestra',texture(note,3.55,'strings',seed=note),0,lev)
    impact(0,.82)
    rise(2.34,1.38,.15)

    chords=[
      (3.75,3.75,38,[50,57,62,65,69],.70),
      (7.50,3.75,34,[46,53,58,62,65],.78),
      (11.25,3.75,41,[53,60,65,69,72],.97),
      (15.00,3.75,38,[50,55,60,64,67],1.02),
      (18.75,3.75,38,[50,57,62,65,69,74],1.13),
      (22.50,1.875,34,[46,53,58,62,65,69],1.13),
      (24.375,1.875,38,[50,55,60,64,67],1.19),
    ]
    for ci,(start,dur,root,notes,energy) in enumerate(chords):
        for j,note in enumerate(notes):
            add('orchestra',texture(note,dur-.12,'strings',seed=ci*100+j),start-.04,
                .050*energy/(len(notes)/5))
        # A warm low brass bed gains presence as the piece develops.
        for j,note in enumerate(notes[:4]):
            add('orchestra',texture(note,dur-.18,'brass',seed=ci*11+j),start,
                .036*energy)
        count=round(dur/(BEAT/2))
        pattern=[notes[0],notes[1],notes[2],notes[1],notes[3],notes[1],notes[2],notes[1]]
        for step in range(count):
            at=start+step*BEAT/2
            if at>25.99: continue
            # A syncopated bass response below the strings.
            if step%4 in [0,1,3]:
                vel=[1,.68,.7,.82][step%4]
                add('bass',bass(root,BEAT*.34,vel),at,.23*energy)
            micro=0 if step==0 else float(RNG.uniform(-.006,.006))
            vel=(.96 if step%4==0 else .58 if step%2 else .76)*float(RNG.uniform(.95,1.03))
            add('ostinato',bowed_pulse(pattern[step%8],BEAT*.29,vel),at+micro,
                .11*energy,(-.34 if step%2==0 else .32))
            if start>=11.25:
                # Quiet octave reinforcement adds scale without chime-like treble.
                add('ostinato',bowed_pulse(pattern[step%8]-12,BEAT*.33,vel),at+.012,
                    .064*energy,-.08)

    # Original four-note call and its longer future-section answer.
    phrases=[
      (7.5,[(65,1.5),(62,.5),(65,1),(69,1)],.046),
      (11.25,[(69,1.5),(72,1.5),(67,1),(65,2),(64,2)],.075),
      (15.0,[(67,2),(69,1),(67,1),(64,2),(62,2)],.082),
      (18.75,[(69,1),(74,2),(77,1),(76,1.5),(74,1.5),(72,1)],.106),
      (22.5,[(74,2),(72,1),(69,1),(67,2),(64,2)],.108),
    ]
    for p,(start,notes,gain) in enumerate(phrases):
        at=start
        for j,(note,beats) in enumerate(notes):
            length=beats*BEAT-.06
            add('horns',texture(note,length,'brass',seed=500+p*10+j),at,gain)
            if start>=18.75:
                add('horns',texture(note-12,length,'brass',seed=600+p*10+j),at+.019,gain*.28)
            at+=beats*BEAT

    # Cinematic rhythm: low drums on downbeats, broad snare/tom backbeats.
    for bar in range(2,14):
        start=bar*BAR
        energy=.64 if bar<6 else .88 if bar<10 else 1.05
        for beat,vel in [(0,1),(1.5,.60),(2,.85),(3.5,.54)]:
            at=start+beat*BEAT
            if at>=26.10:continue
            add('drums',low_drum(vel,.8,1 if beat in [0,2] else 1.28),at,.30*energy,
                -.08 if beat in [0,2] else .22)
        if bar>=4:
            for beat in [1,3]:
                add('drums',war_snare(.82 if beat==1 else 1),start+beat*BEAT+.006,
                    .17*energy,-.16 if beat==1 else .17)
        if bar>=6:
            # Restrained low tom response keeps the pulse cinematic, not dance-like.
            for beat,tune in [(2.75,1.65),(3.25,1.32)]:
                add('drums',low_drum(.55,.45,tune),start+beat*BEAT,.13*energy,
                    -.5 if tune>1.5 else .5)
    for at,power in [(3.75,1),(11.25,1.12),(18.75,1.22)]:
        impact(at,power)
    rise(9.375,1.84,.18)
    rise(16.875,1.84,.20)
    rise(24.375,1.80,.24)
    # Four accelerating low tom hits lead into a tiny breath before the final title.
    for j,beat in enumerate([0,.75,1.25,1.75,2.25,2.75,3.25]):
        at=24.375+beat*BEAT
        add('drums',low_drum(.6+j*.055,.42,1.9-j*.12),at,.22,
            (-.45 if j%2==0 else .45))

    # Final resolved D minor title hit at exactly 26.25. No pulse after the hit.
    final=26.25
    impact(final,1.65)
    add('bass',bass(26,1.55),final,.30)
    for j,note in enumerate([38,45,50,57,62,65,69,74]):
        add('orchestra',texture(note,1.35,'brass',seed=900+j),final,.074)
    for j,note in enumerate([50,57,62,65,69,74]):
        add('orchestra',texture(note,1.80,'strings',seed=1000+j),final,.068)


def reverb(x, seconds, wet, seed):
    """Dense stereo room plus unequal early reflections; no tonal delay taps."""
    result=x.copy()
    rng=np.random.default_rng(seed)
    length=round(seconds*SR)
    t=np.arange(length)/SR
    for ch in range(2):
        ir=band(rng.normal(0,1,length),190,4300 if ch==0 else 3950)
        ir*=np.exp(-t/(seconds/6.5))*np.minimum(t/.028,1)
        ir/=np.sqrt(np.sum(ir*ir))
        # Cross-channel diffuse response preserves width without phase inversion.
        source=.8*x[:,ch]+.2*x[:,1-ch]
        size=1 << ((len(source)+length-2).bit_length())
        tail=np.fft.irfft(np.fft.rfft(source,size)*np.fft.rfft(ir,size),size)[:N]
        result[:,ch]+=wet*tail
    for delay,gain in [(0.029,.14),(.053,.11),(.083,.08),(.127,.055)]:
        d=round(delay*SR)
        result[d:]+=x[:-d,::-1]*gain*wet/.3
    return result


def pcm_write(path, x):
    dither=(RNG.random(x.shape)-RNG.random(x.shape))/65536
    pcm=np.clip(np.rint((x+dither)*32767),-32768,32767).astype('<i2')
    with wave.open(str(path),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes(pcm.tobytes())


def main():
    render_composition()
    mix=np.zeros((N,2))
    # The underlying arrangement grows; this is not a generic crescendo overlay.
    settings={'orchestra':(2.6,.27),'ostinato':(1.25,.14),
              'horns':(2.1,.30),'drums':(1.5,.20),'atmosphere':(2.3,.25)}
    for i,(name,x) in enumerate(STEMS.items()):
        if name in settings:
            sec,wet=settings[name];x=reverb(x,sec,wet,200+i)
        # Stem-specific top-end control keeps the score warm and non-fatiguing.
        top={'bass':1100,'drums':8000,'orchestra':5200,'ostinato':3800,'horns':4800,'atmosphere':6500}[name]
        for ch in range(2):x[:,ch]=band(x[:,ch],25 if name=='bass' else 35,top)
        mix+=x
    # Short breathing space before final hit; do not erase the incoming attack.
    t=np.arange(N)/SR
    dip=(t>26.12)&(t<26.25)
    mix[dip]*=(.55+.45*np.cos((t[dip]-26.12)/.13*np.pi/2))[:,None]
    # Gentle master saturation before a true-peak-aware delivery limiter.
    mix=np.tanh(mix*.92)/.92
    # Finite authored ending: musical decay, then absolute digital silence.
    ending=np.ones(N)
    late=t>28.30
    ending[late]=np.cos(np.clip((t[late]-28.30)/1.30,0,1)*np.pi/2)**2
    ending[t>=29.60]=0
    mix*=ending[:,None]
    mix*=.82/max(np.max(np.abs(mix)),1e-9)
    premaster=OUT/'premaster.f32'
    mix.astype('<f4').tofile(premaster)
    # Floating-point mastering intermediary; output is 24-bit PCM stereo WAV.
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','f32le','-ar',str(SR),
         '-ac','2','-i',str(premaster),
         '-af','loudnorm=I=-15:TP=-1.2:LRA=8:linear=false,aresample=48000,afade=t=out:st=28.3:d=1.3',
         '-ar','48000','-ac','2','-t','30.0','-c:a','pcm_s24le',str(OUT/'score.wav')]
    subprocess.run(cmd,check=True)
    # Ensure the last .4 seconds are exact PCM zero, including dither/resampler tails.
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(OUT/'score.wav'),'-f','f32le','-'])
    final=np.frombuffer(raw,'<f4').reshape(-1,2).copy()
    final[round(29.6*SR):]=0
    final_path=OUT/'score_master.f32'
    final.astype('<f4').tofile(final_path)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','f32le','-ar',str(SR),
                    '-ac','2','-i',str(final_path),'-c:a','pcm_s24le',str(OUT/'score.wav')],check=True)
    sections=[]
    for a,b,title in [(0,3.75,'Intro'),(3.75,11.25,'Forward pulse'),(11.25,18.75,'Escalating tiers'),
                      (18.75,26.25,'Futures lift'),(26.25,30,'Title resolution')]:
        seg=final[round(a*SR):round(b*SR)]
        sections.append({'name':title,'start':a,'end':b,'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(seg**2))+1e-12)),
                         'peak_dbfs':float(20*np.log10(np.max(np.abs(seg))+1e-12))})
    stats={'duration_seconds':len(final)/SR,'sample_rate':SR,'channels':2,'bit_depth':24,
           'peak_dbfs':float(20*np.log10(np.max(np.abs(final)))),
           'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(final**2)))),
           'clipped_samples':int(np.sum(np.abs(final)>=1)),
           'dc_offset':list(map(float,np.mean(final,axis=0))),
           'stereo_correlation':float(np.corrcoef(final.T)[0,1]),
           'last_0_4_seconds_peak':float(np.max(np.abs(final[-round(.4*SR):]))),
           'sections':sections,
           'originality':'Original composition and procedural sound synthesis; no samples, soundfonts, existing recordings, melodies, or generation service used.',
           'tempo':128,'tonality':'D minor; Dm → Bb → F → C/D; final D minor resolution',
           'sync_points':[0,3.75,11.25,18.75,26.25,30]}
    measurement=subprocess.run(['ffmpeg','-hide_banner','-i',str(OUT/'score.wav'),
                    '-af','ebur128=peak=true:framelog=verbose','-f','null','-'],
                    capture_output=True,text=True,check=True)
    summary=measurement.stderr.split('Summary:')[-1]
    (OUT/'loudness.txt').write_text(summary)
    stats['ebu_r128_summary']=summary.strip()
    mono=final.mean(axis=1)
    spectrum=np.abs(np.fft.rfft(mono))**2
    frequencies=np.fft.rfftfreq(len(mono),1/SR)
    stats['energy_fraction_below_20hz']=float(spectrum[frequencies<20].sum()/spectrum.sum())
    stats['energy_fraction_above_8khz']=float(spectrum[frequencies>8000].sum()/spectrum.sum())
    stats['largest_sample_step']=float(np.max(np.abs(np.diff(final,axis=0))))
    (OUT/'analysis.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(json.dumps(stats,indent=2))


if __name__=='__main__':main()
