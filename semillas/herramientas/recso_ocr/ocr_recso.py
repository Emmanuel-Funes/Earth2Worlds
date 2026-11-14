import sys,subprocess,json,re
from PIL import Image
def ocr(im,psm=6):
    p=subprocess.run(['tesseract','stdin','stdout','--psm',str(psm),'-l','spa','-c','preserve_interword_spaces=1'],input=_png(im),capture_output=True)
    return p.stdout.decode('utf-8','ignore')
def _png(im):
    import io;b=io.BytesIO();im.save(b,'PNG');return b.getvalue()
def prep(c,k=3,th=170):
    c=c.resize((c.width*k,c.height*k),Image.BICUBIC);return c.point(lambda v:255 if v>th else 0)
f=sys.argv[1]
im=Image.open(f).convert('L')
if im.size!=(1755,1241): print(json.dumps({'f':f,'skip':'size'}));sys.exit()
head=ocr(prep(im.crop((0,80,1755,260)),2))
if 'LOCALIDAD' not in head.upper(): print(json.dumps({'f':f,'skip':'nohead','head':head[:200]}));sys.exit()
red=Image.open(f).convert('RGB').split()[0]
names=ocr(prep(red.crop((30,295,300,880)),3,90))
rend=''
panel=ocr(prep(im.crop((1400,280,1755,470)),3))
print(json.dumps({'f':f,'head':head,'names':names,'rend':rend,'panel':panel},ensure_ascii=False))
