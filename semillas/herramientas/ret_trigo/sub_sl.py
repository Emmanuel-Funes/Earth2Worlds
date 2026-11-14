import struct,json,collections,sys
def read_shp(p):
    d=open(p,'rb').read(); i=100; shapes=[]
    while i<len(d):
        _,clen=struct.unpack('>ii',d[i:i+8]); i+=8; rec=d[i:i+clen*2]; i+=clen*2
        t=struct.unpack('<i',rec[:4])[0]
        if t!=5: shapes.append(None); continue
        bbox=struct.unpack('<4d',rec[4:36]); np_,npt=struct.unpack('<ii',rec[36:44])
        parts=list(struct.unpack(f'<{np_}i',rec[44:44+4*np_]))+[npt]
        pts=struct.unpack(f'<{2*npt}d',rec[44+4*np_:44+4*np_+16*npt])
        rings=[[(pts[2*k],pts[2*k+1]) for k in range(parts[a],parts[a+1])] for a in range(np_)]
        shapes.append((bbox,rings))
    return shapes
def inside(x,y,rings):
    c=False
    for r in rings:
        n=len(r)
        for k in range(n):
            x1,y1=r[k];x2,y2=r[k-1]
            if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def dbf(p):
    f=open(p,'rb'); h=f.read(32); n,hl,rl=struct.unpack('<IHH',h[4:12]); fl=[]
    while True:
        d=f.read(32)
        if d[0]==0x0D: break
        fl.append((d[:11].split(b'\0')[0].decode(),d[16]))
    f.seek(hl); rows=[]
    for _ in range(n):
        r=f.read(rl);p_=1;v={}
        for nm,l in fl: v[nm]=r[p_:p_+l].decode('utf-8','ignore').strip(); p_+=l
        rows.append(v)
    return rows
S=read_shp('Subregiones 2021.shp'); A=dbf('Subregiones 2021.dbf')
def sub(x,y):
    for s,a in zip(S,A):
        if s and s[0][0]<=x<=s[0][2] and s[0][1]<=y<=s[0][3] and inside(x,y,s[1]): return a['SUB_NUM']+' '+a['SUB_NOM']+' ('+a['SUB_ABR']+')'
    return 'fuera'
if __name__=='__main__':
    G=json.load(open('/mnt/project-files/rotaterra/catastro/parcelas-rurales-san-luis.geojson'))
    cnt=collections.Counter(); area=collections.Counter(); dep=collections.defaultdict(collections.Counter)
    print(list(G['features'][0]['properties'].keys()))
    for ft in G['features']:
        g=ft['geometry']; cs=g['coordinates'][0] if g['type']=='Polygon' else g['coordinates'][0][0]
        x=sum(c[0] for c in cs)/len(cs); y=sum(c[1] for c in cs)/len(cs)
        s=sub(x,y); cnt[s]+=1
        pr=ft['properties']; d=next((pr[k] for k in pr if 'dep' in k.lower()),'?'); dep[d][s]+=1
    print(cnt)
    for d,c in sorted(dep.items(),key=lambda x:str(x[0])): print(d,dict(c))
    for nm,(x,y) in {'Villa Mercedes':(-65.46,-33.68),'Granville':(-65.62,-33.98),'Buena Esperanza':(-65.25,-34.76),'Dupuy':(-66.3,-34.0),'San Luis':(-66.34,-33.30),'Tilisarao':(-65.29,-32.73),'Anguil':(-64.01,-36.53),'Manfredi':(-63.75,-31.84),'Bordenave':(-63.02,-37.84),'Carhue':(-62.76,-37.18)}.items(): print(nm,sub(x,y))
