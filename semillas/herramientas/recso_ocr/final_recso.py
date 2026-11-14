import json,re,csv,collections,unicodedata
toc=open('nac/toc.txt').read().splitlines()
# GM sections and sub-region ranges from the index
secc=[];reg=[];excl=None;gm=None
for l in toc:
    m=re.match(r'GRUPO DE MADUREZ (.+?) (\d+)$',l.strip())
    if m: gm=m.group(1).replace('VII - VIII','VII-VIII').replace('VII - VII','VII-VIII').title().replace('Iii','III').replace('Ii','II').replace('Iv','IV').replace('Vi','VI').replace('Vii','VII').replace('Viii','VIII');secc.append((int(m.group(2)),gm.replace('Corto','corto').replace('Largo','largo')))
    m=re.match(r'(?:SUB-)?REGIÓN ([IV]+-\d) (\d+)$',l.strip())
    if m: reg.append((int(m.group(2)),m.group(1)))
    if l.startswith('ESTABLECIDA') : excl=int(l.split()[-1])
excl=430
def at(lst,p):
    v=None
    for a,x in lst:
        if a<=p: v=x
    return v
cells={json.loads(l)['f'].replace('nac/',''):json.loads(l) for l in open('nac/cells.jsonl')}
trials=json.load(open('nac/trials2.json')); rows=list(csv.DictReader(open('nac/filas2.csv')))
cuad={c['cultivar']:c for c in json.load(open('nac/cuadros.json'))}
PROV={'CORDOBA':'Córdoba','BUENOS AIRES':'Buenos Aires','SANTA FE':'Santa Fe','ENTRE RIOS':'Entre Ríos','TUCUMAN':'Tucumán','SALTA':'Salta','CHACO':'Chaco','SAN LUIS':'San Luis','LA PAMPA':'La Pampa','SANTIAGO':'Santiago del Estero','SANTIAGO DELE':'Santiago del Estero','SANTIAGO DEL ESTERO':'Santiago del Estero','CORRIENTES':'Corrientes','RIO NEGRO':'Río Negro','CATAMARCA':'Catamarca','JUJUY':'Jujuy'}
def A(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper().strip()
def n(x):
    x=(x or '').replace('m','').strip(' ,.')
    return x.replace(',','.') if re.fullmatch(r'\d+(,\d+)?',(x or '').replace('m','').strip(' ,.')) else ''
LOC={'CDEL URUGUAY':'C. del Uruguay','C DEL URUGUAY':'C. del Uruguay','PARANA':'Paraná','CTE GRANVILLE':'Cte. Granville','EST ARAOZ':'Est. Araoz','SAENZ PENA':'Sáenz Peña','SAN ANTONIO DE AR':'San Antonio de Areco','CAP DE LOS REMEDIOS':'Capilla de los Remedios','GRAL CABRERA':'Gral. Cabrera','GRAL PICO':'Gral. Pico','GRAL VILLEGAS':'Gral. Villegas','GRAL PAZ':'Gral. Paz','JESUS MARIA':'Jesús María','METAN':'Metán','BURRUYACU':'Burruyacú','BERROTARAN':'Berrotarán','JUNIN':'Junín','MARCOS JUAREZ':'Marcos Juárez','LOS JURIES':'Los Juríes','QUIMILI':'Quimilí','PIQUETE CAVADO':'Piquete Cavado','CHANAR LADEADO':'Chañar Ladeado','CARMEN DE ARECO':'Carmen de Areco','CORRAL DE BUSTOS':'Corral de Bustos',"O'HIGGINS":"O'Higgins",'9 DE JULIO':'9 de Julio','BOLIVAR':'Bolívar'}
out=[];bad=[]
for t in trials:
    c=cells[t['f']]; p=t['pagina']
    f1=c['fila1']
    m=re.search(r'PROVINCIA:\s*(.*?)\s*LOCALIDAD:\s*(.*)$',f1)
    prov=PROV.get(A(m.group(1)).rstrip('.'),'') if m else ''
    loc=(m.group(2) if m else t['localidad'] or '').strip()
    if not prov: bad.append((p,f1))
    rocr=re.search(r'REGI.N:\s*([IVXl1!|]+)\s*-\s*(\d)',f1)
    gm_s=at(secc,p) if p<excl else at([(a,g) for a,g in secc if a>=excl],p)
    region=at(reg,p) if p<excl else ''
    if p>=excl and rocr: region=re.sub(r'[l1!|]','I',rocr.group(1))+'-'+rocr.group(2)
    nota_region=''
    if region=='I-3' and rocr and re.sub(r'[l1!|]','I',rocr.group(1))=='II':
        region='II-3'; nota_region='El índice del informe lo pone en I-3; la planilla dice II-3 (Pampeana Norte). Se usa II-3.'
    ant=c['antecesor'].strip(' —-');ant='' if ant in('0',) else ant.capitalize().replace('Maiz','Maíz')
    out.append(dict(ensayo_id=f"RECSO2526-p{p}",pagina_informe=p,grupo_madurez=gm_s.replace('VIi-VIii','VII-VIII'),subregion=region,provincia=prov,localidad=LOC.get(A(loc),loc.title() if loc.isupper() else loc),
        codigo_ensayo=c['codigo'],epoca_siembra=c['epoca'],fecha_siembra=t['siembra'] or '',fecha_emergencia=c['emergencia'] if re.fullmatch(r'\d+/\d+/\d{4}',c['emergencia']) else '',
        fecha_cosecha=c['cosecha'] if re.fullmatch(r'\d+/\d+/\d{4}',c['cosecha']) else '',antecesor=ant,
        suelo_co_pct=n(c['co']),suelo_nt_pct=n(c['nt']),suelo_mo_pct=n(c['mo']),suelo_ph=n(c['ph']),suelo_p_ppm=n(c['p']),agua_util=c['au'],prof_agua_util=c['pau'],
        rinde_medio_kg_ha=int(t['media']),cv_pct=(t['cv'] or '').strip('%').replace(',','.'),lsd_kg_ha=(t['lsd'] or '').replace('.',''),n_cultivares=t['n'],
        nota_region=nota_region,en_analisis_conjunto='NO (el INTA lo dejó fuera: variación no aceptable, diseño o entrega tardía)' if p>=excl else 'SI',
        control_lectura=f"promedio de las filas leídas difiere {t['desvio_media']*100:.1f}% del MEDIA del informe"))
print('sin provincia',len(bad),bad[:10])
print(collections.Counter(o['provincia'] for o in out)); print(collections.Counter(o['grupo_madurez'] for o in out)); print(collections.Counter(o['subregion'] for o in out))
print(collections.Counter(o['en_analisis_conjunto'][:2] for o in out))
# compare OCR region vs index region
dif=[(t['pagina'],t['region'],o['subregion']) for t,o in zip(trials,out) if t['region'] and o['subregion'] and t['region']!=o['subregion']]
print('region distinta OCR vs indice',len(dif),dif[:15])
json.dump(out,open('nac/ensayos_final.json','w'),ensure_ascii=False)

def ref(o):
    if o['provincia']=='San Luis': return 'SAN_LUIS (ensayo en la provincia)'
    if o['subregion'] in ('II-3','II-5'): return 'SUBREGION_LIMITROFE (RECSO '+o['subregion']+', vecina a San Luis)'
    return 'OTRA_REGION'
for o in out: o['referencia_san_luis']=ref(o)
import sys
dst=sys.argv[1] if len(sys.argv)>1 else 'nac'
FU='https://www.recsoargentina.com/_files/ugd/7ecdbe_ba67e0407e0d49459c087bd8f2d861b4.pdf'
for o in out: o['fuente_url']=FU
w=csv.DictWriter(open(dst+'/recso_soja_2025_26_ensayos.csv','w',newline='',encoding='utf-8'),fieldnames=list(out[0]));w.writeheader();w.writerows(out)
byp={o['pagina_informe']:o for o in out}
R=[]
for r in rows:
    o=byp[int(r['pagina'])]
    R.append(dict(ensayo_id=o['ensayo_id'],grupo_madurez=o['grupo_madurez'],subregion=o['subregion'],provincia=o['provincia'],localidad=o['localidad'],
      cultivar=r['cultivar'],empresa=r['empresa'],rinde_kg_ha=int(r['rinde']),rinde_relativo_pct=round(100*int(r['rinde'])/o['rinde_medio_kg_ha'],1),
      grupo_estadistico=r['sig'],texto_leido=r['cultivar_ocr'],parecido_nombre=r['parecido'],en_analisis_conjunto=o['en_analisis_conjunto'][:2],referencia_san_luis=o['referencia_san_luis']))
w=csv.DictWriter(open(dst+'/recso_soja_2025_26_rindes.csv','w',newline='',encoding='utf-8'),fieldnames=list(R[0]));w.writeheader();w.writerows(R)
C=[]
for c in json.load(open('nac/cuadros.json')):
    C.append(dict(cultivar=c['cultivar'],empresa=c['empresa'],grupo_madurez_recso=c['seccion_gm'],grupo_madurez_declarado=c['gm'],habito=c['habito'],caracteristicas_cuadro=c['resto'],fuente_url=FU))
w=csv.DictWriter(open(dst+'/recso_soja_2025_26_cultivares.csv','w',newline='',encoding='utf-8'),fieldnames=list(C[0]));w.writeheader();w.writerows(C)
print(len(out),len(R),len(C),collections.Counter(o['referencia_san_luis'] for o in out))
