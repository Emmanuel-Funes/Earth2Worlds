import json,re,csv,collections,unicodedata,hashlib,glob,os,sys
d=json.load(open(sys.argv[2] if len(sys.argv)>2 else 'ret/ret_filas.json'))
SITIO=[  # (patrón en el nombre del archivo, sitio, provincia, subregión 2021, cómo se asignó)
 ('marcos_juarez','Marcos Juárez','Córdoba','7 Pampa subhúmeda norte (PBN)','planilla'),
 ('cabildo','Cabildo','Buenos Aires','10 Pampa semiárida sur (PSS)','planilla'),
 ('balcarce','Balcarce','Buenos Aires','5 Pampa serrana (PSE)','planilla'),
 ('ads_2024','Balcarce','Buenos Aires','5 Pampa serrana (PSE)','planilla'),
 ('carhue','Carhué','Buenos Aires','10 Pampa semiárida sur (PSS)','planilla'),
 ('barrow','Barrow (Tres Arroyos)','Buenos Aires','5 Pampa serrana (PSE)','ubicación (la planilla usa el mapa viejo: V)'),
 ('miramar','Miramar','Buenos Aires','5 Pampa serrana (PSE)','ubicación (la planilla usa el mapa viejo: V)'),
 ('anguil','Anguil','La Pampa','9 Pampa semiárida central (PSC)','planilla'),
 ('cerrillos','Cerrillos','Salta','13 Valles subandinos (VSU)','planilla'),
 ('reconquista','Reconquista','Santa Fe','17 Chaco húmedo sur (CHS)','planilla'),
 ('bauza','Burruyacú','Tucumán','13 Valles subandinos (VSU)','planilla'),
 ('famailla','Famaillá','Tucumán','13 Valles subandinos (VSU)','planilla'),
 ('los_altos','Los Altos','Catamarca','13 Valles subandinos (VSU)','planilla'),
 ('monte_redondo','San Agustín (Monte Redondo)','Tucumán','13 Valles subandinos (VSU)','planilla'),
 ('bordenave','Bordenave','Buenos Aires','10 Pampa semiárida sur (PSS)','planilla'),
 ('manfredi','Manfredi','Córdoba','8 Pampa semiárida norte (PSN)','planilla'),
 ('oliveros','Oliveros','Santa Fe','2 Pampa ondulada norte (PON)','planilla'),
 ('parana','Paraná','Entre Ríos','1 Pampa mesopotámica (PME)','planilla'),
 ('rafa','Rafaela','Santa Fe','2 Pampa ondulada norte (PON)','planilla'),
 ('la_dulce','La Dulce','Buenos Aires','5 Pampa serrana (PSE)','planilla'),
 ('pergamino','Pergamino','Buenos Aires','3 Pampa ondulada sur (POS)','planilla'),
 ('pla','Plá','Buenos Aires','6 Pampa subhúmeda sur (PBS)','planilla'),
 ('venado_tuerto','Venado Tuerto','Santa Fe','7 Pampa subhúmeda norte (PBN)','planilla'),
 ('bolivar','Bolívar','Buenos Aires','6 Pampa subhúmeda sur (PBS)','planilla'),
 ('america','América','Buenos Aires','6 Pampa subhúmeda sur (PBS)','planilla'),
 ('pasman','Pasman','Buenos Aires','5 Pampa serrana (PSE)','ubicación (la planilla dice "V Sur", del mapa viejo; está en el borde con PSS)'),
 ('santiago_del_estero','La Abrita','Santiago del Estero','15 Chaco seco sur (CSS)','ubicación (la planilla dice NOA)'),
 ('saenz_pena','Sáenz Peña','Chaco','16 Chaco húmedo norte (CHN)','ubicación'),
 ('las_brenas','Las Breñas','Chaco','16 Chaco húmedo norte (CHN)','ubicación'),
 ('chacabuco','Chacabuco','Buenos Aires','3 Pampa ondulada sur (POS)','ubicación'),
 ('arias','Arias','Córdoba','7 Pampa subhúmeda norte (PBN)','planilla'),
 ('9_de_julio','9 de Julio','Buenos Aires','6 Pampa subhúmeda sur (PBS)','planilla'),
 ('9j','9 de Julio','Buenos Aires','6 Pampa subhúmeda sur (PBS)','planilla'),
 ('burruyacu','Burruyacú','Tucumán','13 Valles subandinos (VSU)','ubicación (la planilla dice NOA)'),
 ('el_abra','El Abra','Tucumán','13 Valles subandinos (VSU)','ubicación (la planilla dice NOA)'),
 ('valles_serranos','Los Altos','Catamarca','13 Valles subandinos (VSU)','planilla'),
 ('losaltos','Los Altos','Catamarca','13 Valles subandinos (VSU)','planilla'),
 ('hilario_ascasubi','Hilario Ascasubi','Buenos Aires','10 Pampa semiárida sur (PSS)','ubicación (la planilla dice "VS", del mapa viejo)'),
 ('roldan','Roldán','Santa Fe','2 Pampa ondulada norte (PON)','ubicación'),
 ('victoria','Victoria','Entre Ríos','1 Pampa mesopotámica (PME)','ubicación'),
 ('mercedes','Mercedes','Corrientes','18 Mesopotamia central (MCE)','planilla'),
 ('cnel_suarez','Pasman','Buenos Aires','5 Pampa serrana (PSE)','ubicación (la planilla dice "V Sur", del mapa viejo; está en el borde con PSS)'),
 ('balcerce','Balcarce','Buenos Aires','5 Pampa serrana (PSE)','planilla'),
 ('benito_juarez','Benito Juárez','Buenos Aires','5 Pampa serrana (PSE)','ubicación (la planilla dice IV, del mapa viejo)'),
 ('pli_','Plá','Buenos Aires','6 Pampa subhúmeda sur (PBS)','ubicación'),
 ('la_abrita','La Abrita','Santiago del Estero','15 Chaco seco sur (CSS)','ubicación (la planilla dice NOA)'),
 ('pena','Sáenz Peña','Chaco','16 Chaco húmedo norte (CHN)','ubicación'),
]
def sitio(a):
    a=re.sub(r'[\s.-]+','_',unicodedata.normalize('NFKD',a).encode('ascii','ignore').decode().lower())
    for p,*r in SITIO:
        if p in a: return r
    raise SystemExit('sin sitio '+a)
def A(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()
PREF=['BO','B','K','E','BIOSEMINIS','BIOCEMINIS','BIOCERES','BIOC','MSINTA','IMSINTA','MSI','MDABONAERENSE','MDBONAERENSE','MDABONE','MDABON','MDB','MDA','MD','BONAERENSE','BON','MB','KLEIN','KL','BUCK','BK','DM','LG','IS','RGT','RAGT','GROBO','TBIO','BAGUETTE','BAG','ACA','BIO','TUC','MS']
TYPO={'FULGOOR':'FULGOR','ZAETA':'SAETA','GUYABO':'GUAYABO','PICASO':'PICAZO','PICAZZO':'PICAZO','PICASSO':'PICAZO','ESTANIO':'ESTANO','CIEN':'100ANOS','CIENANOS':'100ANOS',
      'QUIRICO':'QUIRIKO','QUIRI':'QUIRIKO','ARASA':'ARAZA','GINKGO':'GINGKO','LAHUEL':'LAHUEN','LEHUEN':'LAHUEN','MIGRON':'MIGNON','JACARAN':'JACARANDA','COLIH':'COLIHUE',
      'ELITTE17':'ELITE17','ELITTE43':'ELITE43','WA110169':'PAMPERO','WA11':'PAMPERO','WA110169PAMPERO':'PAMPERO','EXPARCE':'ARCE','SELENIO':'SELENIOCL','B370502':'370502'}
def compacto(n):
    s=A(str(n)).replace('Ã','')
    s=re.sub(r'\((PAMPERO|HB4|BAGUETTE)\)',r'\1',s)
    return re.sub(r'[^A-Z0-9]','',s)
def candidatos(n):
    s=re.sub(r'(HB4|BAGUETTE)$','',compacto(n)); vistos=set(); pila=[s]
    while pila:
        x=pila.pop()
        if x in vistos: continue
        vistos.add(x)
        for p in PREF:
            if x.startswith(p) and len(x)>len(p)+1: pila.append(x[len(p):])
    return {TYPO.get(x,x) for x in vistos}
filas=[r for r in d if 'RELLENO' not in str(r['cultivar']).upper()]
porclave=collections.defaultdict(collections.Counter)
base=collections.Counter()
for r in filas:
    for c in candidatos(r['cultivar']): base[c]+=1
def clave(n):
    cs=candidatos(n)
    return max(cs,key=lambda c:(base[c],-len(c)))
for r in filas: r['clave']=clave(r['cultivar']); porclave[r['clave']][re.sub(r'\s+',' ',str(r['cultivar']).strip())]+=1
nombre={k:max(c.items(),key=lambda x:(len(x[0])>3 and not x[0].isdigit(),x[1]))[0] for k,c in porclave.items()}
ens={}
for r in filas:
    s=sitio(r['archivo']+' '+r['localidad']); key=(r['campana'],r['archivo'],r['bloque'])
    e=ens.setdefault(key,dict(ensayo_id='RET-'+hashlib.md5('|'.join(key).encode()).hexdigest()[:8],campana=r['campana'],sitio=s[0],provincia=s[1],subregion_2021=s[2],subregion_como=s[3],
        localidad_planilla=r['localidad'],subregion_planilla=r['subregion'],epoca_y_manejo=r['bloque'],
        fungicida='CON' if 'CON F' in r['bloque'].upper() else 'SIN' if 'SIN F' in r['bloque'].upper() else 'sin dato',archivo=r['archivo'],filas=[]))
    e['filas'].append(r)
SL={'9 Pampa semiárida central (PSC)':'SAN_LUIS_MISMA_SUBREGION (PSC, la del este de San Luis)','8 Pampa semiárida norte (PSN)':'SEMIARIDA_VECINA (PSN)','10 Pampa semiárida sur (PSS)':'SEMIARIDA_VECINA (PSS)'}
E=[];R=[]
URL={**{f'{y}/{(y+1)%100:02d}':f'https://www.argentina.gob.ar/{"inase/" if y in (2011,2014,2015,2016,2017,2018,2020,2021,2022) else ""}red-de-ensayos-comparativos-de-variedades-de-trigo/campana-{y}{y+1}' for y in range(2018,2023)},'2025/26':'https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/campana-20252026','2024/25':'https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/campana-20242025','2023/24':'https://www.argentina.gob.ar/inase/red-de-ensayos-comparativos-de-variedades-de-trigo/campana-20232024'}
for key,e in ens.items():
    fl=e.pop('filas')
    import statistics
    unidad='kg/ha'
    if statistics.median(r['rinde_kg_ha'] for r in fl)<30:  # la planilla vino en t/ha
        unidad='t/ha en la planilla, pasado a kg/ha'
        for r in fl: r['rinde_kg_ha']*=1000
    e['unidad_original']=unidad
    # mismo cultivar dos veces en un ensayo: se promedia y se avisa
    g=collections.defaultdict(list)
    for r in fl: g[r['clave']].append(r)
    media=sum(r['rinde_kg_ha'] for r in fl)/len(fl)
    e.update(n_cultivares=len(g),rinde_medio_kg_ha=round(media),repeticiones=max(r['reps'] for r in fl),referencia_san_luis=SL.get(e['subregion_2021'],'OTRA_REGION'),fuente_url=URL[e['campana']])
    E.append(e)
    for k,rs in g.items():
        rv=round(sum(r['rinde_kg_ha'] for r in rs)/len(rs))
        R.append(dict(ensayo_id=e['ensayo_id'],campana=e['campana'],sitio=e['sitio'],subregion_2021=e['subregion_2021'],fungicida=e['fungicida'],
            cultivar=nombre[k],clave_nombre=k,nombre_en_planilla='; '.join(sorted({str(r['cultivar']).strip() for r in rs})),rinde_kg_ha=rv,
            rinde_relativo_pct=round(100*rv/media,1),repeticiones=rs[0]['reps'],referencia_san_luis=e['referencia_san_luis']))
dst=sys.argv[1]
for nm,T in (('ensayos',E),('rindes',R)):
    w=csv.DictWriter(open(f'{dst}/ret_trigo_{min(e["campana"] for e in E)[:4]}_{int(max(e["campana"] for e in E)[:4])+1}_{nm}.csv','w',newline='',encoding='utf-8'),fieldnames=list(T[0]));w.writeheader();w.writerows(T)
print(len(E),len(R),len(nombre))
print(collections.Counter(e['referencia_san_luis'] for e in E))
amb=[n for k,n in nombre.items() if k.isdigit()]
print('nombres solo numero',amb)
