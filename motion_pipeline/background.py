"""background.py — generic smooth-gradient background, generated as browser-side JS (Task 4).

The float-field math is ported from PGCube's gbg.js ALGORITHM (linear + Gaussian glow in
OKLab, chroma x1.15 with exact Rec.709 luma restore, dot lattice, monochrome TPDF dither) —
but every colour comes from the scheme's Palette; no client CD constants appear here.

generate_background_page(palette, w, h, opts) -> HTML string painting one frame at time T
(opts: {'banded': True} quantises chroma to simulate an 8-bit 4:2:0 intermediate — the
gate's known-bad discriminant; {'sample_text': str} draws sample text for the menu test).
The same generated JS is what real scenes embed, so the menu's background test and the full
render share one code path (anti-goal: no divergent test path).
"""
import json

OKLAB_JS = r"""
const s2l = v => { v /= 255; return v <= 0.04045 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
const l2s = v => 255*(v <= 0.0031308 ? 12.92*v : 1.055*Math.pow(Math.max(v,0), 1/2.4) - 0.055);
function toOklab(r,g,b){ r=s2l(r); g=s2l(g); b=s2l(b);
  const l=Math.cbrt(0.4122214708*r+0.5363325363*g+0.0514459929*b),
        m=Math.cbrt(0.2119034982*r+0.6806995451*g+0.1073969566*b),
        s=Math.cbrt(0.0883024619*r+0.2817188376*g+0.6299787005*b);
  return [0.2104542553*l+0.7936177850*m-0.0040720468*s,
          1.9779984951*l-2.4285922050*m+0.4505937099*s,
          0.0259040371*l+0.7827717662*m-0.8086757660*s]; }
function fromOklab(L,a,b){ const l=(L+0.3963377774*a+0.2158037573*b)**3,
        m=(L-0.1055613458*a-0.0638541728*b)**3, s=(L-0.0894841775*a-1.2914855480*b)**3;
  return [l2s(4.0767416621*l-3.3077115913*m+0.2309699292*s),
          l2s(-1.2684380046*l+2.6097574011*m-0.3413193965*s),
          l2s(-0.0041960699*l-0.7034186147*m+1.7076147010*s)]; }
function mulberry32(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t; return (t^t>>>14)>>>0; }; }
"""

PAGE_TMPL = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
canvas{{display:block}}
#txt{{position:absolute;left:8%;top:40%;color:{TEXT};font:700 {FS}px sans-serif}}
</style></head><body>
<canvas id="bg" width="{W}" height="{H}"></canvas>
<div id="txt">{SAMPLE}</div>
<script>
{OKLAB}
const W={W}, H={H}, STOPS={STOPS}, PARTICLE={PARTICLE}, TEXT={TEXT}, BANDED={BANDED};
const SAT=1.15, GLOW={{cx:0.5, cy:0.42, sx:0.45, sy:0.9}};
function hex(h){{ return [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)]; }}
function mixHex(h1,h2,t){{ const a=hex(h1),b=hex(h2);
  return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t]; }}
const stops=STOPS.map(hex), particle=hex(PARTICLE);
const field=new Float32Array(W*H*3);
for(let y=0;y<H;y++){{ const Y=(y+.5)/H, dy=(Y-GLOW.cy)*0.5625/GLOW.sy;
  for(let x=0;x<W;x++){{ const X=(x+.5)/W, dx=(X-GLOW.cx)/GLOW.sx,
    g=Math.exp(-0.5*(dx*dx+dy*dy)), o=(y*W+x)*3;
    // linear gradient across the stops along X, plus gaussian glow toward the last stop
    const n=stops.length-1, ft=Math.min(Math.max(X,0),1)*n, i=Math.floor(ft), ft2=ft-i;
    const base=mixHex(STOPS[Math.min(i,n)], STOPS[Math.min(i+1,n)], ft2);
    let c=base.map((v,k)=> v + (stops[n][k]-v)*0.85*g);
    const [L,A,B]=toOklab(c[0],c[1],c[2]), c1=fromOklab(L,A*SAT,B*SAT);
    const d=0.2126*(c[0]-c1[0])+0.7152*(c[1]-c1[1])+0.0722*(c[2]-c1[2]);
    for(let k=0;k<3;k++) field[o+k]=c1[k]+d; }} }}
// dot lattice (static dots for the test frame)
const S=Math.max(24, Math.round(W/24)), nc=Math.ceil(W/S)+2, nr=Math.ceil(H/S)+2;
const rnd0=mulberry32(2207);
for(let j=0;j<nr;j++) for(let i=0;i<nc;i++){{
  const cx=(i+.5)*S, cy=(j+.5)*S, bm=0.55+0.75*(rnd0()+rnd0()+rnd0())/4294967296/3*3;
  const al=Math.min(0.30, 0.20*bm);
  const rr=1.5, ext=rr+0.5;
  for(let py=Math.floor(cy-ext);py<=Math.ceil(cy+ext);py++){{ if(py<0||py>=H) continue;
    for(let px=Math.floor(cx-ext);px<=Math.ceil(cx+ext);px++){{ if(px<0||px>=W) continue;
      const cov=Math.min(1,Math.max(0,ext-Math.hypot(px+.5-cx,py+.5-cy))); if(cov<=0) continue;
      const a=al*cov, o=(py*W+px)*3;
      for(let k=0;k<3;k++) field[o+k]+=(particle[k]-field[o+k])*a; }} }} }}
const cv=document.getElementById('bg'), ctx=cv.getContext('2d'), img=ctx.createImageData(W,H);
const rnd=mulberry32(12345), S16=1/65536, A=2.0, C=0.35;
const BW=W>>1, NB=new Float32Array(Math.max(1,BW*(H>>1)));
for(let i=0;i<NB.length;i++){{ const r=rnd(); NB[i]=A*C*((r&0xFFFF)-(r>>>16))*S16; }}
// known-bad mode: 4:2:0-style chroma — Cb/Cr averaged per 2x2 block, then quantised to even
// 8-bit codes — producing wide plateaus with sharp boundaries (the real 8-bit staircase)
let BCB=null, BCR=null;
if(BANDED){{
  BCB=new Float32Array(BW*(H>>1)); BCR=new Float32Array(BW*(H>>1));
  for(let by=0;by<(H>>1);by++) for(let bx=0;bx<BW;bx++){{
    let R=0,G=0,Bb=0;
    for(let dy=0;dy<2;dy++) for(let dx=0;dx<2;dx++){{
      const o=((by*2+dy)*W+(bx*2+dx))*3; R+=field[o]; G+=field[o+1]; Bb+=field[o+2]; }}
    R/=4; G/=4; Bb/=4;
    BCB[by*BW+bx]=Math.round((128-0.1179*R-0.2864*G+0.4043*Bb)/2)*2;
    BCR[by*BW+bx]=Math.round((128+0.4043*R-0.3390*G-0.0653*Bb)/2)*2; }}
}}
for(let y=0,p=0;y<H;y++){{ const br=(y>>1)*BW;
  for(let x=0;x<W;x++,p++){{ const o=p*3,q=p*4;
    const r=rnd(), n=A*(1-C)*((r&0xFFFF)-(r>>>16))*S16 + NB[br+(x>>1)];
    let R=field[o]+n, G=field[o+1]+n, B=field[o+2]+n;
    if(BANDED){{
      const Y=0.2126*R+0.7152*G+0.0722*B, bi=br+(x>>1);
      R=Y+1.5748*(BCR[bi]-128); G=Y-0.1873*(BCB[bi]-128)-0.4681*(BCR[bi]-128); B=Y+1.8556*(BCB[bi]-128); }}
    img.data[q]=R; img.data[q+1]=G; img.data[q+2]=B; img.data[q+3]=255; }} }}
ctx.putImageData(img,0,0);
</script></body></html>
"""


def generate_background_page(palette, width=1920, height=1080, sample_text='Sample', banded=False):
    """Full HTML page painting one background frame (plus optional sample text)."""
    return PAGE_TMPL.format(
        W=width, H=height, FS=max(12, height // 12),
        OKLAB=OKLAB_JS,
        STOPS=json.dumps(palette['gradient_stops']),
        PARTICLE=json.dumps(palette['particle_colour']),
        TEXT=json.dumps(palette['text']),
        BANDED='true' if banded else 'false',
        SAMPLE=sample_text,
    )
