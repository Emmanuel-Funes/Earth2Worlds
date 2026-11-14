import openpyxl,glob,re,json,unicodedata,warnings,collections
warnings.filterwarnings('ignore')
def A(s): return unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
def norm(s): return re.sub(r'\s+',' ',A(s)).strip()
CAMP={'d2526':'2025/26','d2024':'2024/25','d2023':'2023/24'}
out=[];ens=[];visto=set();log=[]
for f in sorted(glob.glob('gir/d*/*.xlsx')):
    camp=CAMP[f.split('/')[1]]
    wb=openpyxl.load_workbook(f,data_only=True)
    for ws in wb.worksheets:
        rows=list(ws.iter_rows(values_only=True))
        top=[str(r[0]) for r in rows[:6] if r and r[0]]
        loc=next((t for t in top if 'LOCALIDAD' in t.upper()),None)
        if not loc: continue
        sitio=re.sub(r'\(.*','',loc.split(':',1)[1]).strip()
        sitio=re.sub(r'\s+-\s+Santa Fe','',sitio)
        k=(camp,norm(sitio))
        if k in visto: continue
        fs=next((t.split(':',1)[1].strip() for t in top if 'SIEMBRA' in t.upper()),'')
        h=next((i for i,r in enumerate(rows[:15]) if r and r[0] and norm(r[0]) in ('cultivar','hibrido')),None)
        if h is None: log.append((f,ws.title,'sin cabecera'));continue
        H=[norm(v) if v else '' for v in rows[h]]
        ci=next((i for i,v in enumerate(H) if v.startswith('rendimiento de granos')),None)
        ai=next((i for i,v in enumerate(H) if v.startswith('aceite')),None)
        ji=next((i for i,v in enumerate(H) if v.startswith('rendimiento ajustado') and 'relativ' not in v),None)
        if ci is None: log.append((f,ws.title,'sin columna de rinde',H[:10]));continue
        filas=[]
        for r in rows[h+1:]:
            if not r or r[0] is None: 
                if filas: break
                continue
            nm=re.sub(r'\s+',' ',str(r[0]).replace('\xa0',' ')).strip()
            if re.match(r'(promedio|media|cv|dms|lsd|desv)',norm(nm)): break
            v=r[ci]
            if not isinstance(v,(int,float)) or v<=0: continue
            filas.append(dict(nombre=nm,empresa=str(r[1] or '').strip(),rinde=float(v),aceite=r[ai] if ai is not None and isinstance(r[ai],(int,float)) else None,ajustado=r[ji] if ji is not None and isinstance(r[ji],(int,float)) else None))
        if not filas: log.append((f,ws.title,'sin filas'));continue
        visto.add(k)
        ens.append(dict(campana=camp,sitio=sitio,fecha_siembra=fs,localidad_planilla=loc,archivo=f.split('/')[-1],hoja=ws.title,n=len(filas)))
        for x in filas: out.append(dict(campana=camp,sitio=sitio,**x))
for l in log: print(l)
print(len(ens),len(out)); 
for e in ens: print(e['campana'],e['sitio'],e['n'],e['fecha_siembra'])
json.dump(dict(ensayos=ens,filas=out),open('gir/gir.json','w'),ensure_ascii=False)
