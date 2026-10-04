"""Original motion graphics for AI Money Map; no browser capture or stock footage.

Render a 30-second film from the saved research snapshot. Requires Pillow, NumPy,
and regular/bold fonts; MP4 output also requires FFmpeg on PATH. Each layout is
composed independently, never cropped from the other.
"""
from __future__ import annotations
import argparse, functools, json, math, os, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / 'dist/circulation.json').read_text())
SCENARIOS = json.loads((ROOT / 'dist/scenarios.json').read_text())
COMPANIES = json.loads((ROOT / 'dist/data.json').read_text())['companies']
AVENIR = Path('/System/Library/Fonts/Avenir Next.ttc')
DEFAULT_SITE_URL = 'https://github.com/hehamalainen/followthemoney'
_font_faces = None
MINT=(168,246,215); BLUE=(116,204,236); GOLD=(237,191,121)
WHITE=(235,244,241); DIM=(132,166,177); CORAL=(236,142,121)
COLORS={'investment':MINT,'commercial':BLUE,'finance':(189,171,242),
        'guarantee':GOLD,'noncash':(231,164,199),'supplier':(126,170,188)}
NAMES={'MSFT':'Microsoft','OPENAI':'OpenAI','NVDA':'NVIDIA','CRWV':'CoreWeave',
       'DELL':'Dell','TSM':'TSMC','AMAT':'Applied Materials','ONTO':'Onto',
       'ORCL':'Oracle','BE':'Bloom Energy','SBENERGY':'SB Energy','MU':'Micron',
       'FN':'Fabrinet','GOOGL':'Alphabet','AMZN':'Amazon','ANTHROPIC':'Anthropic',
       'SKHYNIX':'SK hynix','BROOKFIELD':'Brookfield','LRCX':'Lam Research'}
TIERS={k:1 for k in ['MSFT','OPENAI','ANTHROPIC','AMZN','GOOGL','META','ORCL']}
TIERS.update({k:2 for k in ['NVDA','CRWV','DELL','TSM','MU','SKHYNIX','FN','SOLIDIGM','NBIS','SNPS']})
CHAPTERS=[
 (0,3.75,'THE AI ECONOMY',['AI IS NOT','A STRAIGHT LINE.'],'Follow the money.',[]),
 (3.75,7.5,'01 / THE FIRST TIER',['INVESTOR.','CUSTOMER.','SUPPLIER.'],'One relationship. Different obligations.',
  ['msft-oai-funding','oai-msft-cloud']),
 (7.5,11.25,'02 / THE SECOND TIER',['BEYOND','THE CHIP.'],'Equity. Hardware. Conditional support.',
  ['nvda-crwv-equity','downstream_crwv_dell','downstream_dell_nvda','nvda-crwv-backstop']),
 (11.25,15,'03 / INTO THE FACTORY',['SILICON BECOMES','FACTORIES.'],'The chain reaches further than the headline.',
  []),
 (15,18.75,'04 / THE PHYSICAL WORLD',['POWER HAS','A RETURN PATH.'],'Procurement. Non-cash shares. Guarantees.',
  ['downstream_oracle_bloom','downstream_bloom_oracle_equity','oai-sb-lease','nvda-sb-guarantee']),
 (18.75,26.25,'05 / THE FOURTH DIMENSION',['WHO CAPTURES','WHAT COMES NEXT?'],'100 public companies. Three conditional futures.',[]),
 (26.25,30,'ENTER THE ATLAS',['AI MONEY','MAP.'],'Follow the capital. Challenge the future.',[]),
]
CHAPTERS[3][-1].extend(next(c for c in DATA['cases'] if c['id']=='downstream_silicon_cascade')['edgeIds'])

def ease(x):
    x=max(0,min(1,x));return x*x*(3-2*x)

def configure_fonts(regular=None, bold=None):
    """Resolve each weight once; collection indices never leak into TTF files."""
    global _font_faces
    windows_fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    candidates = [
        ((str(AVENIR), 2), (str(AVENIR), 8)),
        (('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 0),
         ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 0)),
        (('/usr/share/fonts/dejavu/DejaVuSans.ttf', 0),
         ('/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf', 0)),
        (('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', 0),
         ('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf', 0)),
        ((str(windows_fonts / 'arial.ttf'), 0),
         (str(windows_fonts / 'arialbd.ttf'), 0)),
        # Pillow can also resolve installed fonts by name on supported systems.
        (('DejaVuSans.ttf', 0), ('DejaVuSans-Bold.ttf', 0)),
    ]

    def loadable(face):
        ImageFont.truetype(face[0], 24, index=face[1])
        return face

    def explicit(path, weight):
        path = Path(path).expanduser()
        index = weight if path.resolve() == AVENIR.resolve() else 0
        try:
            return loadable((str(path), index))
        except (OSError, ValueError) as exc:
            role = 'bold' if weight == 8 else 'regular'
            raise ValueError(
                f'Cannot load {role} font {str(path)!r} (face {index}). '
                f'Pass a readable font file with --font-{role}; separate TTF/OTF '
                'files use face 0. Only the built-in Avenir collection uses '
                'faces 2 and 8.'
            ) from exc

    chosen = [explicit(regular, 2) if regular else None,
              explicit(bold, 8) if bold else None]
    if None in chosen:
        for pair in candidates:
            try:
                # Prefer a matching family when discovering missing defaults.
                loadable(pair[0]); loadable(pair[1])
            except (OSError, ValueError):
                continue
            chosen = [chosen[i] or pair[i] for i in range(2)]
            break
    if None in chosen:
        raise ValueError(
            'No usable regular/bold font pair found. Install DejaVu Sans '
            '(Debian/Ubuntu: fonts-dejavu-core), or provide both '
            '--font-regular /path/Regular.ttf and --font-bold /path/Bold.ttf.'
        )
    _font_faces = tuple(chosen)
    font.cache_clear()


@functools.lru_cache(maxsize=140)
def font(size,weight=2):
    if _font_faces is None:
        configure_fonts()
    path, index = _font_faces[1 if weight == 8 else 0]
    return ImageFont.truetype(path, int(size), index=index)

@functools.lru_cache(maxsize=128)
def orb(color,size):
    # Painted radial light plus a small shaded core, original code-native asset.
    yy,xx=np.mgrid[-size:size,-size:size];r=np.sqrt(xx*xx+yy*yy)/size
    glow=np.exp(-r*6)*.47 + np.exp(-r*r*90)*.45
    alpha=np.clip(glow*255,0,255).astype('uint8')
    arr=np.empty((size*2,size*2,4),dtype='uint8');arr[:,:,:3]=color;arr[:,:,3]=alpha
    im=Image.fromarray(arr);d=ImageDraw.Draw(im)
    rad=size*.15
    d.ellipse((size-rad,size-rad,size+rad,size+rad),fill=color+(235,),outline=WHITE+(240,),width=1)
    d.ellipse((size-rad*.6,size-rad*.65,size+rad*.03,size+rad*.02),fill=(239,255,250,245))
    return im

class Film:
    def __init__(self,vertical=False,site_url=DEFAULT_SITE_URL):
        self.site_url = site_url
        self.vertical=vertical;self.w,self.h=(1080,1920) if vertical else (1920,1080)
        self.cx,self.cy=(540,1090) if vertical else (1320,535)
        yy,xx=np.mgrid[0:self.h,0:self.w]
        halo=np.exp(-((xx/self.w-.69)**2/.11+(yy/self.h-.46)**2/.2))
        self.bg=Image.fromarray(np.stack([4+halo*6,10+halo*17,17+halo*19],axis=-1).astype('uint8'))
        rng=np.random.default_rng(2603);self.stars=rng.random((240,3))
        self.nodes={n['id']:n for n in DATA['nodes']};self.edges={e['id']:e for e in DATA['edges']}
        self.positions={}
        for tier in (1,2,3):
            ids=[n for n in self.nodes if TIERS.get(n,3)==tier]
            for i,id in enumerate(ids):
                angle=i/len(ids)*math.tau+tier*.57;r=[235,365,505][tier-1]
                self.positions[id]=np.array([math.cos(angle)*r,(tier-2)*150+math.sin(i*2.2)*24,math.sin(angle)*r])
        self.layouts=[None,
          {'MSFT':(-240,-80,-20),'OPENAI':(220,110,60)},
          {'NVDA':(0,-250,-40),'CRWV':(-300,170,50),'DELL':(300,170,-10)},None,
          {'ORCL':(-260,-210,0),'BE':(250,-140,20),'OPENAI':(-250,210,40),'SBENERGY':(230,260,30),'NVDA':(180,60,-220)},None,None]

    def project(self,p,yaw,pitch,scale=1,center=None):
        x,y,z=p;cy,sy=math.cos(yaw),math.sin(yaw);cp,sp=math.cos(pitch),math.sin(pitch)
        x,z=x*cy+z*sy,-x*sy+z*cy;y,z=y*cp-z*sp,y*sp+z*cp
        persp=1600/(1600+z);cx,cy=center or (self.cx,self.cy)
        return (cx+x*persp*scale,cy+y*persp*scale,z,persp)

    def text(self,draw,text,x,y,size=30,color=WHITE,weight=2,alpha=1,align='left',maxwidth=None):
        f=font(size,weight)
        if maxwidth:
            while draw.textlength(text,font=f)>maxwidth and size>15:
                size-=1;f=font(size,weight)
        if align=='center':x-=draw.textlength(text,font=f)/2
        elif align=='right':x-=draw.textlength(text,font=f)
        draw.text((x,y),text,font=f,fill=color+(int(255*alpha),),stroke_width=0)

    def network(self,im,t,stage,local,opacity=1):
        glow=Image.new('RGB',(self.w//2,self.h//2));gd=ImageDraw.Draw(glow)
        draw=ImageDraw.Draw(im,'RGBA')
        intro=stage in (0,6)
        focusids=CHAPTERS[stage][-1]
        focus=set(x for id in focusids for x in (self.edges[id]['from'],self.edges[id]['to']))
        yaw=(-.3+t*.045) if intro else -.14+math.sin(local*.36)*.19
        pitch=.42 if intro else .24
        points=dict(self.positions)
        if self.layouts[stage]:points.update({k:np.array(v,dtype=float) for k,v in self.layouts[stage].items()})
        if stage==3:
            top=['NVDA','TSM'];points.update({'NVDA':np.array([0,-300,0]),'TSM':np.array([0,-70,0])})
            rest=sorted(focus-set(top))
            for i,k in enumerate(rest):
                a=math.pi*.15+i/max(1,len(rest)-1)*math.pi*.7
                points[k]=np.array([math.cos(a)*440,150+math.sin(a)*160,math.sin(i)*80])
        scale=.88 if self.vertical else 1.07
        if intro:scale*=.74+ease(local/(3.75 if stage==0 else 2))*.18
        if stage==6:scale*=.75
        proj={k:self.project(p,yaw,pitch,scale) for k,p in points.items()}
        # Structural orbital traces give the camera a legible volume.
        for tier in (1,2,3):
            ring=[]
            for a in np.linspace(0,math.tau,120):
                r=[235,365,505][tier-1];p=self.project((math.cos(a)*r,(tier-2)*150,math.sin(a)*r),yaw,pitch,scale)
                ring.append(p[:2])
            draw.line(ring,fill=DIM+(int((25 if intro else 12)*opacity),),width=1)
        for i,e in enumerate(DATA['edges']):
            hot=not focusids or e['id'] in focusids
            strength=(.76 if hot else .045)*opacity
            a,b=points[e['from']],points[e['to']]
            path=[]
            for u in np.linspace(0,1,50):
                bend=70+(i%5)*19
                p=a*(1-u)+b*u+np.array([math.sin(i*2.3)*36,-bend,math.cos(i*2.3)*65])*math.sin(math.pi*u)
                path.append(self.project(p,yaw,pitch,scale)[:2])
            color=COLORS[e['flowType']]
            end=int(len(path)*ease((local-.08*(i%4))/.9)) if hot and not intro else len(path)
            visible=path[:max(2,end)]
            if e['flowType'] in ('guarantee','supplier'):
                for j in range(0,len(visible)-2,4):draw.line(visible[j:j+3],fill=color+(int(strength*180),),width=3 if hot else 1)
            else:draw.line(visible,fill=color+(int(strength*180),),width=3 if hot else 1)
            if hot:
                gd.line([(x/2,y/2) for x,y in visible],fill=tuple(int(c*strength*.5) for c in color),width=4)
                # Directional route highlights; not volumes or cash settlement.
                if e['flowType'] not in ('supplier','guarantee','noncash'):
                    for offset in (0,.5):
                        pos=(t*.27+i*.17+offset)%1;j=min(47,int(pos*48));p=path[j]
                        trail=path[max(0,j-4):j+1]
                        if len(trail)>1:draw.line(trail,fill=color+(int(opacity*210),),width=3)
                        sprite=orb(color,17);im.paste(sprite,(int(p[0])-17,int(p[1])-17),sprite)
                # Small fixed arrow to identify direction on every relation.
                j=32;px,py=path[j];vx,vy=np.array(path[j])-np.array(path[j-1]);mag=math.hypot(vx,vy) or 1;vx/=mag;vy/=mag
                draw.polygon([(px+vx*5,py+vy*5),(px-vx*5-vy*3,py-vy*5+vx*3),(px-vx*5+vy*3,py-vy*5-vx*3)],fill=color+(int(strength*230),))
        im=ImageChops.add(im,glow.filter(ImageFilter.GaussianBlur(4)).resize(im.size,Image.Resampling.BILINEAR))
        draw=ImageDraw.Draw(im,'RGBA')
        label_boxes=[]
        for k,p in sorted(proj.items(),key=lambda kv:-kv[1][2]):
            hot=not focusids or k in focus
            alpha=opacity*(1 if hot else .13)
            color=[MINT,BLUE,GOLD][TIERS.get(k,3)-1]
            radius=int((63 if focusids and hot else 37)*min(1.3,p[3]))
            sprite=orb(color,radius).copy()
            if alpha<.99:sprite.putalpha(sprite.getchannel('A').point(lambda a:int(a*alpha)))
            im.paste(sprite,(int(p[0])-radius,int(p[1])-radius),sprite)
            if hot:
                rr=(14 if focusids else 8)*p[3]
                draw.ellipse((p[0]-rr,p[1]-rr,p[0]+rr,p[1]+rr),outline=color+(int(alpha*170),),width=1)
                label=NAMES.get(k,self.nodes[k].get('ticker') or k)
                show=bool(focusids) or k in ['NVDA','OPENAI','MSFT','ANTHROPIC','AMZN','GOOGL','ORCL','TSM','ASML','BE','CRWV','DELL','META']
                if show and 45<p[0]<self.w-45 and 40<p[1]<self.h-170:
                    lw=draw.textlength(label,font=font(28 if focusids else 21));box=(p[0]-lw/2-8,p[1]+rr+15,p[0]+lw/2+8,p[1]+rr+48)
                    if intro and any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in label_boxes):continue
                    label_boxes.append(box)
                    self.text(draw,label,p[0],p[1]+rr+15,28 if focusids else 21,color=WHITE,alpha=alpha,align='center',maxwidth=210 if self.vertical else 290)
        return im

    def future(self,im,t,local):
        draw=ImageDraw.Draw(im,'RGBA');year=2026+4*ease(local/6.6)
        centers=[(250,1080),(540,1330),(830,1080)] if self.vertical else [(985,650),(1360,565),(1720,650)]
        for lens,(cx,cy) in enumerate(centers):
            scale=(.48 if self.vertical else .52);spin=local*.13+lens*.3
            growth=np.interp(year,[2026,2027,2028,2029,2030],SCENARIOS['scenarios'][lens]['path'])/100
            radius=270*(1+(growth-1)*.2)
            for ringy in (-70,70):
                ring=[self.project((math.cos(a)*radius,ringy,math.sin(a)*radius),spin,.46,scale,(cx,cy))[:2] for a in np.linspace(0,math.tau,85)]
                draw.line(ring,fill=DIM+(65,),width=1)
            for i,c in enumerate(COMPANIES):
                score=SCENARIOS['profiles'][c['ticker']]['scores'][lens]
                a=i*2.39996;r=radius*math.sqrt((i+1)/100)
                y=(i%4-1.5)*40-score*(year-2026)*28
                p=self.project((math.cos(a)*r,y,math.sin(a)*r),spin,.46,scale,(cx,cy))
                col=MINT if score>=2 else BLUE if score>0 else DIM if score==0 else CORAL
                size=15 if score>=2 else 10;sp=orb(col,size);im.paste(sp,(int(p[0])-size,int(p[1])-size),sp)
            label=['BUILDOUT','DIFFUSION','RESET'][lens]
            self.text(draw,label,cx,cy+170 if self.vertical else cy+225,24 if self.vertical else 26,color=WHITE,align='center')
            self.text(draw,str(round(growth*100))+' / SPEND INDEX',cx,cy+210 if self.vertical else cy+265,17,color=DIM,align='center')
        x1,x2=(95,985) if self.vertical else (780,1825);y=1600 if self.vertical else 944
        draw.line((x1,y,x2,y),fill=DIM+(85,),width=2)
        progress=(year-2026)/4;draw.line((x1,y,x1+(x2-x1)*progress,y),fill=MINT+(255,),width=4)
        xx=x1+(x2-x1)*progress;sp=orb(MINT,22);im.paste(sp,(int(xx)-22,int(y)-22),sp)
        self.text(draw,'2026',x1,y+17,20,color=DIM)
        self.text(draw,'2030',x2,y+17,20,color=MINT,align='right')
        return im

    def frame(self,t):
        stage=next(i for i,s in enumerate(CHAPTERS) if s[0]<=t<s[1])
        start,end,kicker,lines,deck,_=CHAPTERS[stage];local=t-start
        im=self.bg.copy();draw=ImageDraw.Draw(im,'RGBA')
        for x,y,r in self.stars:
            x=x*self.w;y=(y*self.h+t*(2+r*3))%self.h
            draw.ellipse((x,y,x+1+r,y+1+r),fill=(147,195,205,30+int(r*60)))
        if stage==5:im=self.future(im,t,local)
        else:im=self.network(im,t,stage,local,opacity=.55 if stage==6 else 1)
        # A quiet gradient protects typography while the volume passes behind it.
        shade=Image.new('RGBA',im.size);sd=ImageDraw.Draw(shade)
        if not self.vertical:
            for x in range(0,900,5):sd.rectangle((x,100,x+5,900),fill=(4,10,17,int(220*(1-x/900)**1.6)))
        else:
            for y in range(130,720,5):sd.rectangle((0,y,self.w,y+5),fill=(4,10,17,int(160*(1-(y-130)/590))))
        im=Image.alpha_composite(im.convert('RGBA'),shade).convert('RGB');draw=ImageDraw.Draw(im,'RGBA')
        margin=80 if self.vertical else 96
        draw.line((margin,125,self.w-margin,125),fill=(91,133,151,70),width=1)
        self.text(draw,'AI MONEY MAP',margin,63,24,weight=8,color=MINT)
        self.text(draw,'A FILM ABOUT FINANCIAL INTERDEPENDENCE',self.w-margin,67,17,color=DIM,align='right',maxwidth=self.w-440)
        # Fade and lift text at musical edit points, without strobes.
        enter=ease(local/.46);leave=1-ease((local-(end-start-.26))/.26) if stage!=6 else 1
        alpha=enter*leave;lift=(1-enter)*24
        tx=margin;ty=(205 if self.vertical else 220)+lift
        self.text(draw,kicker,tx,ty,21,color=MINT,alpha=alpha)
        if stage==6:
            ty=300 if self.vertical else 285
            for j,line in enumerate(lines):self.text(draw,line,tx,ty+j*(155 if self.vertical else 146),150 if self.vertical else 140,weight=8,color=WHITE if j==0 else MINT,alpha=alpha,maxwidth=self.w-160 if self.vertical else 980)
            self.text(draw,deck,tx,ty+345,29 if self.vertical else 31,color=WHITE,alpha=alpha,maxwidth=self.w-160)
            self.text(draw,'EXPLORE THE EVIDENCE',tx,ty+424,22,color=MINT,alpha=alpha)
            self.text(draw,self.site_url,tx,ty+467,25 if self.vertical else 24,color=DIM,alpha=alpha,maxwidth=self.w-160)
        else:
            size=90 if self.vertical else 94;step=107 if self.vertical else 108
            if stage==5 and not self.vertical:size=75;step=92
            for j,line in enumerate(lines):self.text(draw,line,tx,ty+56+j*step,size,weight=8,color=MINT if j==len(lines)-1 else WHITE,alpha=alpha,maxwidth=self.w-160 if self.vertical else 750 if stage!=5 else 665)
            decky=ty+76+len(lines)*step
            self.text(draw,deck,tx,decky,27 if self.vertical else 25,color=DIM,alpha=alpha,maxwidth=self.w-160 if self.vertical else 650)
        # Scene-specific statements use only the saved disclosure context.
        detail=[('43 COUNTERPARTIES','59 DOCUMENTED RELATIONSHIPS'),
          ('$11.9B FUNDED','$250B AZURE COMMITMENT'),
          ('EQUITY + PROCUREMENT','CONDITIONAL CAPACITY SUPPORT'),
          ('SUPPLIER RELATIONSHIPS','INDIVIDUAL SPEND UNDISCLOSED'),
          ('NON-CASH CUSTOMER SHARES','CONTINGENT LEASE SUPPORT'),
          ('',''),('100 PUBLIC COMPANIES','3 CONDITIONAL FUTURES')][stage]
        if detail[0]:
            dy=1600 if self.vertical else 896
            if self.vertical:
                self.text(draw,detail[0],margin,dy,24,color=MINT,alpha=alpha)
                self.text(draw,detail[1],margin,dy+46,24,color=WHITE,alpha=alpha)
            else:
                self.text(draw,detail[0],margin,dy,23,color=MINT,alpha=alpha)
                self.text(draw,detail[1],margin,dy+41,20,color=DIM,alpha=alpha)
        if stage==1:
            self.text(draw,'MICROSOFT / OPENAI · DISTINCT DISCLOSED MEASURES',margin,1715 if self.vertical else 970,17,color=DIM,alpha=alpha,maxwidth=self.w-margin*2)
        if stage==4:
            self.text(draw,'ORACLE / BLOOM AND OPENAI / SB ENERGY ARE SEPARATE PATHS',margin,1715 if self.vertical else 970,17,color=DIM,alpha=alpha,maxwidth=self.w-margin*2)
        if stage==5:
            self.text(draw,'SCENARIOS, NOT FORECASTS',95 if self.vertical else 96,1695 if self.vertical else 845,20,color=DIM)
            self.text(draw,'ILLUSTRATIVE SPEND INDEX / 2026 = 100',95 if self.vertical else 96,1730 if self.vertical else 887,19,color=DIM)
            self.text(draw,'COLOR: BUSINESS ADVANTAGE / VULNERABILITY',95 if self.vertical else 96,1760 if self.vertical else 920,17,color=DIM)
        # Persistent context remains readable without sound.
        fy=self.h-85;draw.line((margin,fy-25,self.w-margin,fy-25),fill=(91,133,151,75),width=1)
        self.text(draw,'DISCLOSURES THROUGH 03 OCT 2026',margin,fy,17,color=DIM)
        self.text(draw,'RELATIONSHIPS, NOT TRACKED CASH',self.w-margin,fy+30 if self.vertical else fy,17,color=DIM,align='right')
        progress=t/30;draw.rectangle((0,self.h-4,int(self.w*progress),self.h),fill=MINT+(200,))
        return im

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vertical',action='store_true',help='Render the 1080×1920 portrait layout.')
    p.add_argument('--output',required=True,help='MP4 destination, or output prefix with --stills.')
    p.add_argument('--audio',help='Optional soundtrack file; requires FFmpeg for MP4 output.')
    p.add_argument('--stills',action='store_true',help='Render seven chapter JPEGs only; no FFmpeg required.')
    p.add_argument('--font-regular',metavar='FILE',help='Regular font file (TTF/OTF face 0). Default: Avenir on macOS, then DejaVu/Liberation/Arial.')
    p.add_argument('--font-bold',metavar='FILE',help='Bold font file (TTF/OTF face 0). Pass both font flags for a custom family.')
    p.add_argument('--site-url',default=DEFAULT_SITE_URL,help='Closing-card destination (default: %(default)s).')
    a=p.parse_args()
    try:
        configure_fonts(a.font_regular, a.font_bold)
    except ValueError as exc:
        p.error(str(exc))
    movie=Film(a.vertical, a.site_url);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    if a.stills:
        for i,t in enumerate([2,5.7,9.5,13.3,16.8,23.5,28]):movie.frame(t).save(out.parent/f'{out.stem}-{i}.jpg',quality=93)
        return
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{movie.w}x{movie.h}','-r','30','-i','-']
    if a.audio:cmd+=['-i',a.audio]
    cmd+=['-c:v','libx264','-preset','medium','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709']
    if a.audio:cmd+=['-c:a','aac','-b:a','256k','-ar','48000']
    cmd+=['-t','30',str(out)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for i in range(900):
        proc.stdin.write(movie.frame(i/30).tobytes())
        if i%150==0:print(f'{"vertical" if a.vertical else "wide"}: {i}/900 frames',flush=True)
    proc.stdin.close();code=proc.wait()
    if code:raise SystemExit(code)
    print(f'Created {out}: {out.stat().st_size/1e6:.1f} MB',flush=True)

if __name__=='__main__':main()
