import sys,json,subprocess,io
from PIL import Image
f,mode,th,k=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
im=Image.open(f).convert('RGB')
ch={'r':im.split()[0],'g':im.convert('L'),'b':im.split()[2]}[mode]
c=ch.crop((30,295,300,1000)); c=c.resize((c.width*k,c.height*k),Image.BICUBIC).point(lambda v:255 if v>th else 0)
b=io.BytesIO();c.save(b,'PNG')
o=subprocess.run(['tesseract','stdin','stdout','--psm','6','-c','preserve_interword_spaces=1'],input=b.getvalue(),capture_output=True).stdout.decode()
print(json.dumps({'f':f,'cfg':f'{mode}{th}x{k}','names':o}))
