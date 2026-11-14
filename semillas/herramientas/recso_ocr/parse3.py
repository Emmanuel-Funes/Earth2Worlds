import json,re,csv,difflib,unicodedata
pages=[l.strip() for l in open('nac/img_pages.txt')]
cult=json.load(open('nac/cuadros.json'))
secc=[(13,'III corto'),(61,'III largo'),(104,'IV corto'),(158,'IV largo'),(226,'V corto'),(294,'V largo'),(326,'VI corto'),(378,'VI largo'),(404,'VII-VIII'),(999,'')]
def seccion(p):
    for (a,g),(b,_) in zip(secc,secc[1:]):
        if a<=p<b: return g
def k(s): return re.sub(r'[^A-Z0-9]','',unicodedata.normalize('NFKD',s.upper()).encode('ascii','ignore').decode()).replace('€','E')
def fix(s): return s.replace('€','E')
canon={}
for c in cult: canon.setdefault(c['seccion_gm'],[]).append(c)
allc=cult
MAN={'86540':'BG 540','GARGARSF':'64R64RSF','G4RGARSF':'64R64RSF','GARGARSE':'64R64RSF','PSDAO2SCE':'P80A02SCE'}
def match(name,gm):
    if name in MAN: return [c for c in allc if c['cultivar']==MAN[name]][0],0.99
    cand=canon.get(gm,[])+allc
    kn=k(fix(name)); best=None;bs=0
    for c in cand:
        r=difflib.SequenceMatcher(None,kn,k(c['cultivar'])).ratio()
        if r>bs: bs,best=r,c
    return best,bs
def num(x):
    try: return float(x.replace('/','7').replace('.','').replace(',','.'))
    except: return None
alt={}
for l in open('nac/alt.jsonl'):
    a=json.loads(l); alt.setdefault(a['f'].replace('nac/',''),[]).append((a['cfg'],a['names']))
def parse_names(txt,gm):
    entradas=[]
    for x in txt.splitlines():
        x=x.strip(' |')
        mm=re.match(r'(.+?)\s{2,}[\]\|\-\s]*(\d[\d/]{2,5})\s*_?\s*([+a]?)\s*[\]\|]?\s*$',x) or re.match(r'(.+)\s+[\]\|\-\s]*(\d[\d/]{2,5})\s*_?\s*([+a]?)\s*[\]\|]?\s*$',x)
        if not mm or 'ENTRADA' in x.upper() or 'PROMED' in x.upper(): continue
        nm=mm.group(1).strip(' |]-'); dg=re.sub(r'\D','',mm.group(2).replace('/','7')); r=int(dg[:4]) if len(dg)>=4 else int(dg)
        c,score=match(nm,gm)
        entradas.append(dict(cultivar_ocr=nm,cultivar=c['cultivar'] if score>=0.75 else '',empresa=c['empresa'] if score>=0.75 else '',parecido=round(score,2),rinde=r,sig=mm.group(3)))
    return entradas
def dev(e,media):
    return abs(sum(x['rinde'] for x in e)/len(e)-media)/media if media and e else None
trials=[];rows=[];bad=[]
for l in open('nac/ocr2.jsonl'):
    d=json.loads(l)
    if d.get('skip'): continue
    idx=int(re.search(r'p-(\d+)',d['f']).group(1)); page=int(pages[idx]); gm=seccion(page)
    h=d['head']
    m=re.search(r'PROVINCIA:\s*(.+?)\s+LOCALIDAD:\s*(.+)',h); prov,loc=(m.group(1).strip(),m.group(2).strip()) if m else (None,None)
    if prov is None:
        m=re.search(r'LOCALIDAD:\s*(.+)',h); loc=m.group(1).strip() if m else None
    rg=re.search(r'REGI[OÓ]N:\s*([IVXl1!|]+)\s*-\s*(\d)',h); reg=(rg.group(1).replace('l','I').replace('1','I').replace('!','I').replace('|','I')+'-'+rg.group(2)) if rg else None
    sie=(re.search(r'SIEMBRA:\s*([\d/]+)',h) or [0,None])[1]
    ant=(re.search(r'Antecesor:\s*(.+)',h) or [0,None])[1]
    cod=(re.search(r'\b(\d{2}[A-Z]{2,4}\d\w+)',h) or [0,None])[1]
    soil=None;ls=h.splitlines()
    for i,x in enumerate(ls):
        if 'Suelos' in x:
            for y in ls[i+1:i+3]:
                if re.search(r'\d,\d',y): soil=re.sub(r'\s+',' ',y.split(cod)[0] if cod and cod in y else y).strip();break
    p=d['panel']; pm=lambda kk:(re.search(kk+r'\s*=?\s*([\d.,/]+)',p,re.I) or [None,None])[1]
    media=num(pm('MEDIA') or ''); cv=pm('C[Vv]'); lsd=pm('LSD')
    entradas=parse_names(d['names'],gm); cfg='r90x3'
    ok=dev(entradas,media)
    if ok is not None and ok>=0.02 or ok is None:
        for c2,txt in alt.get(d['f'],[]):
            e2=parse_names(txt,gm); o2=dev(e2,media)
            if o2 is None: continue
            sc2=(o2>=0.02,sum(1 for x in e2 if not x['cultivar']),o2); sc1=(ok is None or ok>=0.02,sum(1 for x in entradas if not x['cultivar']),ok if ok is not None else 9)
            if sc2<sc1: entradas,ok,cfg=e2,o2,c2
    t=dict(pagina=page,seccion_gm=gm,region=reg,provincia=prov,localidad=loc,siembra=sie,antecesor=ant,codigo=cod,suelo_co_mo_ph=soil,media=media,cv=cv,lsd=lsd,n=len(entradas),desvio_media=round(ok,3) if ok is not None else None,ocr=cfg,f=d['f'])
    trials.append(t)
    for e in entradas: rows.append({**{k2:t[k2] for k2 in ('pagina','seccion_gm','region','provincia','localidad','codigo')},**e})
import collections
print('ensayos',len(trials),'filas',len(rows))
print('media coincide (<2%)',sum(1 for t in trials if t['desvio_media'] is not None and t['desvio_media']<0.02),'sin dato',sum(1 for t in trials if t['desvio_media'] is None))
print('filas sin match',sum(1 for r in rows if not r['cultivar']))
json.dump(trials,open('nac/trials2.json','w'),ensure_ascii=False,indent=0)
w=csv.DictWriter(open('nac/filas2.csv','w',newline=''),fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)
