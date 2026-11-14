import openpyxl,glob,re,json,sys,warnings,collections
warnings.filterwarnings('ignore')
def val(ws_rows,label):
    for r in ws_rows:
        for i,v in enumerate(r):
            if isinstance(v,str) and v.strip().lower().startswith(label.lower()):
                rest=[x for x in r[i+1:] if x not in (None,'')]
                return rest
    return []
out=[];log=[]
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv)>1 else 'ret/x*/*.xls*')):
    camp=f.split('/')[1][1:5]+'/'+f.split('/')[1][7:9]
    try: wb=openpyxl.load_workbook(f,read_only=True,data_only=True)
    except Exception as e: log.append((f,'no abre',str(e)[:60]));continue
    if 'Rendimiento' not in wb.sheetnames: log.append((f,'sin hoja Rendimiento',wb.sheetnames[:6]));continue
    D=list(wb['Datos'].iter_rows(max_row=110,max_col=10,values_only=True)) if 'Datos' in wb.sheetnames else []
    sub=val(D,'Subregión'); loc=val(D,'Localidad')
    R=list(wb['Rendimiento'].iter_rows(values_only=True))
    n=0
    for i,r in enumerate(R):
        for j,v in enumerate(r):
            if v=='Rep I':
                # block label: look up to 3 rows above same col for ÉPOCA
                lab=next((R[k][j] for k in range(i-1,max(i-4,-1),-1) if isinstance(R[k][j],str) and ('POCA' in R[k][j].upper() or 'FUNG' in R[k][j].upper())),None)
                if lab is None: continue
                if 'POCA' not in lab.upper():  # planillas viejas: el ciclo va en una fila 'Ciclo: ...' arriba del bloque
                    ciclo=next((R[k][0] for k in range(i-1,max(i-9,-1),-1) if isinstance(R[k][0],str) and R[k][0].strip().lower().startswith('ciclo')),None)
                    if ciclo: lab=f"{ciclo.strip()} {lab.strip()}"
                # columna de nombres: el 'Cultivar' más cercano a la izquierda, en esta fila o la de arriba
                cand=[q for q in range(j) if r[q]=='Cultivar' or (i>0 and q<len(R[i-1]) and R[i-1][q]=='Cultivar')]
                cc=max(cand) if cand else j-1
                # rep columns until 'Promedio'
                reps=[]; k=j
                while k<len(r) and r[k]!='Promedio': reps.append(k); k+=1
                for rr in R[i+1:i+60]:
                    if rr[cc] in (None,0,'') or not isinstance(rr[cc],(str,int)) : 
                        if rr[0] is None and rr[cc] is None and all(x is None for x in rr[j:j+3]): pass
                        continue
                    nm=str(rr[cc]).strip().rstrip('_').strip()
                    if nm in('0','') or re.match(r'(CV|DMS|LSD|MEDIA|PROMEDIO)\b',nm.upper()): continue
                    rv=[x for x in (rr[q] for q in reps) if isinstance(x,(int,float)) and x>0]
                    if not rv: continue
                    out.append(dict(campana=camp,archivo=f.split('/')[-1],subregion=' '.join(map(str,sub[:1])),localidad=' '.join(map(str,loc[:2])),bloque=(lab.strip()+(f' (época {rr[0]})' if r[0]=='Epoca' else '')),cultivar=nm,reps=len(rv),rinde_kg_ha=sum(rv)/len(rv),promedio_planilla=rr[k] if k<len(rr) else None))
                    n+=1
    log.append((f.split('/')[-1],camp,sub[:1],loc[:2],n))
for l in log: print(l)
json.dump(out,open(sys.argv[2] if len(sys.argv)>2 else 'ret/ret_filas.json','w'),ensure_ascii=False)
print(len(out))
