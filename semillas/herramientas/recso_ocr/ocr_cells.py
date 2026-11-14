import sys,subprocess,json,io
from PIL import Image
C={'co':(247,311),'nt':(317,371),'mo':(378,433),'ph':(439,493),'p':(506,559),'au':(583,654),'pau':(661,737),'fn':(982,1047),'fp':(1053,1107),'fk':(1114,1169),'fs':(1179,1234),'codigo':(1246,1487),'epoca':(1503,1629)}
f=sys.argv[1]; im=Image.open(f).convert('L')
out={'f':f}
for k,(a,b) in C.items():
    c=im.crop((a+3,178,b-3,206)); c=c.resize((c.width*4,c.height*4),Image.BICUBIC).point(lambda v:255 if v>160 else 0)
    if c.getextrema()[0]==255: out[k]='';continue
    bb=io.BytesIO();c.save(bb,'PNG')
    wl=[] if k in('codigo','epoca') else ['-c','tessedit_char_whitelist=0123456789,.m']
    out[k]=subprocess.run(['tesseract','stdin','stdout','--psm','7','-l','spa']+wl,input=bb.getvalue(),capture_output=True).stdout.decode().strip()
for k,(a,b,y0,y1) in {'antecesor':(1365,1720,113,148),'gm':(545,680,78,112),'emergencia':(640,780,113,148),'cosecha':(985,1110,113,148),'fila1':(0,1755,78,112)}.items():
    c=im.crop((a,y0,b,y1)); c=c.resize((c.width*3,c.height*3),Image.BICUBIC).point(lambda v:255 if v>160 else 0)
    bb=io.BytesIO();c.save(bb,'PNG')
    out[k]=subprocess.run(['tesseract','stdin','stdout','--psm','7','-l','spa'],input=bb.getvalue(),capture_output=True).stdout.decode().strip()
print(json.dumps(out,ensure_ascii=False))
