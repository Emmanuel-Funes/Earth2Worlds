import json,csv,re,unicodedata,collections,hashlib,sys
D=json.load(open('gir/gir.json'))
D['filas']=[r for r in D['filas'] if r['nombre'].strip().lower()!='cultivar']
def A(s): return unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().upper()
SUF=['CLPLUS','CLP','CLDM','CLHO','HOCL','CL','HO','AO','DM','CP','INTA','L']
PRE=['ES','BUCK','BGH','BKH','ALZ','KLEIN','EXP','INSUN','SYN','NK']
TYPO={'12227':'1227','WOLLF':'WOLF','211B22':'211','8243':'8243'}
def cands(n):
    s=re.sub(r'[^A-Z0-9]','',A(n)); vis=set(); st=[s]
    while st:
        x=st.pop()
        if x in vis or not x: continue
        vis.add(x)
        for f in SUF:
            if x.endswith(f) and len(x)>len(f)+2: st.append(x[:-len(f)])
        for p in PRE:
            if x.startswith(p) and len(x)>len(p)+2: st.append(x[len(p):])
    out=set()
    for x in vis:
        for a,b in TYPO.items(): x=x.replace(a,b)
        out.add(x)
    return out
base=collections.Counter(c for r in D['filas'] for c in cands(r['nombre']))
def clave(n):
    if re.fullmatch(r'(T ?|TESTIGO ?)\d',A(n).strip()): return 'TESTIGO'+re.sub(r'\D','',n)
    return max(cands(n),key=lambda c:(base[c],-len(c)))
SITIO={'reconquista':('Reconquista','Santa Fe'),'florencia':('Florencia','Santa Fe'),'miramar':('Miramar','Buenos Aires'),'pieres':('Pieres','Buenos Aires'),
 'coronel suarez':('Coronel Suárez','Buenos Aires'),'anguil':('Anguil','La Pampa'),'pergamino':('Pergamino','Buenos Aires'),'bolivar':('Bolívar','Buenos Aires'),
 'p. r. saenz pena':('Sáenz Peña','Chaco'),'saenz pena':('Sáenz Peña','Chaco'),'villa ocampo':('Villa Ocampo','Santa Fe'),'rafaela':('Rafaela','Santa Fe'),'ceres':('Ceres','Santa Fe'),
 'laboulaye':('Laboulaye','Córdoba'),'trenque lauquen':('Trenque Lauquen','Buenos Aires'),'pehuajo':('Pehuajó','Buenos Aires'),'balcarce':('Balcarce','Buenos Aires'),
 'general pico':('General Pico','La Pampa'),'general pinedo':('General Pinedo','Chaco'),'los juries':('Los Juríes','Santiago del Estero'),'saliquelo':('Salliqueló','Buenos Aires'),
 'laprida':('Laprida','Buenos Aires'),'tandil':('Tandil','Buenos Aires'),'jesus maria':('Jesús María','Córdoba'),'manfredi':('Manfredi','Córdoba'),'humboldt':('Humboldt','Santa Fe')}
REF={'Anguil':'SEMIARIDA_VECINA (centro-este de La Pampa)','General Pico':'SEMIARIDA_VECINA (noreste de La Pampa)','Laboulaye':'SEMIARIDA_VECINA (sur de Córdoba)',
     'Trenque Lauquen':'OESTE_BONAERENSE','Salliqueló':'OESTE_BONAERENSE','Pehuajó':'OESTE_BONAERENSE'}
def A2(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower().strip()
nombres=collections.defaultdict(collections.Counter)
for r in D['filas']: nombres[clave(r['nombre'])][r['nombre']]+=1
canon={k:max(c.items(),key=lambda x:(x[1],x[0].isupper()))[0] for k,c in nombres.items()}
E=[];R=[]
URL='https://asagir.org.ar/acerca-de-red-de-ensayos-de-girasol-inta-asagir-463'
for e in D['ensayos']:
    s,prov=SITIO[A2(e['sitio'])]
    eid='GIR-'+hashlib.md5((e['campana']+s).encode()).hexdigest()[:8]
    fl=[r for r in D['filas'] if r['campana']==e['campana'] and r['sitio']==e['sitio']]
    media=sum(r['rinde'] for r in fl)/len(fl)
    E.append(dict(ensayo_id=eid,campana=e['campana'],sitio=s,provincia=prov,fecha_siembra=e['fecha_siembra'],n_cultivares=len(fl),rinde_medio_kg_ha=round(media),
        referencia_san_luis=REF.get(s,'OTRA_REGION'),archivo=e['archivo'],hoja=e['hoja'],fuente_url=URL))
    for r in fl:
        R.append(dict(ensayo_id=eid,campana=e['campana'],sitio=s,cultivar=canon[clave(r['nombre'])],empresa=r['empresa'],
            es_testigo_anonimo='SI' if clave(r['nombre']).startswith('TESTIGO') else 'NO',rinde_kg_ha=round(r['rinde']),
            rinde_relativo_pct=round(100*r['rinde']/media,1),aceite_pct=round(r['aceite'],1) if r['aceite'] else '',
            rinde_ajustado_aceite_kg_ha=round(r['ajustado']) if r['ajustado'] else '',nombre_en_planilla=r['nombre'],referencia_san_luis=REF.get(s,'OTRA_REGION')))
dst=sys.argv[1]
for nm,T in (('ensayos',E),('rindes',R)):
    w=csv.DictWriter(open(f'{dst}/girasol_inta_asagir_2023_2026_{nm}.csv','w',newline='',encoding='utf-8'),fieldnames=list(T[0]));w.writeheader();w.writerows(T)
print(len(E),len(R),len(canon),collections.Counter(e['referencia_san_luis'] for e in E))
