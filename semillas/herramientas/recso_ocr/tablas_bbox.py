import re,json,subprocess,html
from collections import defaultdict
PAG={14:'III corto',62:'III largo',105:'IV corto',159:'IV largo',227:'V corto',295:'V largo',327:'VI corto',379:'VI largo',405:'VII-VIII'}
out=[];rep=[]
for p,gm in PAG.items():
    x=subprocess.run(['pdftotext','-bbox','-f',str(p),'-l',str(p),'nac/recso.pdf','-'],capture_output=True,text=True).stdout
    W=[(float(a),float(b),float(c),float(d),html.unescape(t)) for a,b,c,d,t in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<',x)]
    # stop at testigo section
    ycut=min([w[1] for w in W if w[4]=='PROMEDIO']+[1e9])
    W=[w for w in W if w[1]<ycut-2]
    per=[w for w in W if re.fullmatch(r'\d\d/\d\d',w[4])]
    regs=sorted([w for w in W if re.fullmatch(r'I{1,3}-\d',w[4])])
    per.sort()
    colreg=[];g=-1;prev=None
    for w in per:
        if prev is None or w[4]<=prev: g+=1
        prev=w[4]; colreg.append(regs[g][4])
    assert g==len(regs)-1
    cols=[((w[0]+w[2])/2,f"{colreg[i]} {w[4]}") for i,w in enumerate(per)]
    yper=per[0][1]
    lines=defaultdict(list)
    for w in W:
        if w[1]>yper+3: lines[round((w[1]+w[3])/2)].append(w)
    # merge close y
    ys=sorted(lines); rows=[];cur=None
    for y in ys:
        if cur and y-cur[0]<=2: cur[1].extend(lines[y])
        else: cur=[y,list(lines[y])]; rows.append(cur)
    xnum=cols[0][0]-12
    for y,ws in rows:
        ws.sort()
        name=' '.join(w[4] for w in ws if w[2]<xnum and not (w is ws[0] and w[4].isdigit()))
        if not name: continue
        if 'ENSAYOS' in name: name='Nº ENSAYOS'
        vals={}
        for w in ws:
            if w[0]>=xnum and w[4].isdigit():
                c=(w[0]+w[2])/2; k=min(range(len(cols)),key=lambda q:abs(cols[q][0]-c))
                if abs(cols[k][0]-c)>9: rep.append((gm,name,w[4],'lejos',round(abs(cols[k][0]-c),1)))
                if cols[k][1] in vals: rep.append((gm,name,'dup'))
                vals[cols[k][1]]=int(w[4])
        out.append(dict(gm=gm,cultivar=name,vals=vals))
    T=[o for o in out if o['gm']==gm]
    print(gm,len(cols),[(o['cultivar'],len(o['vals'])) for o in T if o['cultivar']=='Nº ENSAYOS' or set(o['vals'].values())=={100}],len(T)-1)
print(rep[:30],len(rep))
json.dump(out,open('nac/tablas_rr.json','w'),ensure_ascii=False,indent=0)
# Después se pasa a semillas/datos/recso_soja_2025_26_multianual.csv (formato largo) y se igualan 6 nombres
# abreviados en las tablas a los del Cuadro: BG540, STINE 50EE59, NEO 50S23 RR, BRV7525SCE, DM 50E25 SE, STINE 52EF52.
