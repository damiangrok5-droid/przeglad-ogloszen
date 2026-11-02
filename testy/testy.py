"""Bramki przed publikacją. Każda bramka zwraca PASS/FAIL (albo POMINIETO z jawnym powodem) z liczbami; FAIL daje kod wyjścia ≠ 0 i blokuje publikację.
Użycie: python3 testy/testy.py --stan stan/stan.json.gz --dane strona/dane --build _site [--repo .]
Pliki pomocnicze testy_danych.py i zakazane.json pochodzą z zaszyfrowanego pakietu (narzedzia/pakiet.py otworz).
Lista nazw wykluczonych: wyłącznie lokalnie, poza repo – plik wskazany zmienną PLIK_WYKLUCZEN albo ../lokalne/nazwy_wykluczone.txt
(względem katalogu repo), jedna nazwa w wierszu. Brak pliku (np. w CI) = ten jeden podpunkt POMINIETO z komunikatem.
SITE_PASSWORD (opcjonalnie): odszyfrowanie i porównanie buildu ze źródłem."""
import json, os, re, sys, glob, gzip, subprocess, argparse, collections, importlib.util
ap=argparse.ArgumentParser(); ap.add_argument('--stan'); ap.add_argument('--dane',default='strona/dane'); ap.add_argument('--build'); ap.add_argument('--repo',default='.')
ap.add_argument('--strona',default='strona'); ap.add_argument('--wynik'); ap.add_argument('--prog-precyzji',type=float,default=0.9)
A=ap.parse_args(); W=[]
def enc_ok(p):
    # dozwolone formaty: JSON {iv,ct} (szyfruj.mjs) albo binarny "PO1"|sól|iv|szyfrogram (stan.mjs)
    b=open(p,'rb').read()
    if b[:3]==b'PO1': return len(b)>3+16+12+16
    try: return set(json.loads(b.decode('utf-8')))=={'iv','ct'}
    except Exception: return False
def wynik(nazwa,ok,**liczby):
    st=ok if isinstance(ok,str) else ('PASS' if ok else 'FAIL'); W.append({'test':nazwa,'wynik':st,**liczby}); print(f"{st}  {nazwa}  {json.dumps(liczby,ensure_ascii=False)[:600]}",flush=True)
ST=None
if A.stan: ST=json.load(gzip.open(A.stan,'rt',encoding='utf-8') if A.stan.endswith('.gz') else open(A.stan,encoding='utf-8'))
TD=None; p=os.path.join(A.repo,'testy','testy_danych.py')
if os.path.exists(p): sp=importlib.util.spec_from_file_location('td',p); TD=importlib.util.module_from_spec(sp); sp.loader.exec_module(TD)
pz=os.path.join(A.repo,'testy','zakazane.json'); ZK=json.load(open(pz,encoding='utf-8')) if os.path.exists(pz) else None
# 1–2. testy merytoryczne danych (z pakietu)
dod={}
if ST:
    if TD: dod=TD.uruchom(ST,A,wynik) or {}
    else: wynik('testy_danych',False,powod='brak testy/testy_danych.py – najpierw: python3 narzedzia/pakiet.py otworz')
# 3. skan danych osobowych (dane strony przed szyfrowaniem + stan bez okien dowodów są maskowane przy ekstrakcji)
JEDN='|'.join((ZK or {}).get('jednostki_po_liczbie') or ['zł','pln','eur','szt','tys','mln'])  # pełna lista w pakiecie
UUID=re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
RX={'email':r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}','telefon':r'(?<![\d/.,-])(?:\+48[\s-]?)?(?:\d{3}[\s-]\d{3}[\s-]\d{3}|\(\d{2}\)\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\d{2}[\s-]\d{3}[\s-]\d{2}[\s-]\d{2})(?![\d/.,-])(?!\s*(?:'+JEDN+'))',
    'pesel':r'(?<![\d\w-])\d{11}(?![\d\w-])','iban':r'\bPL\s?\d{2}(?:\s?\d{4}){6}\b','tel_slowo':r'(?i)\b(tel\.?|telefon|fax)\s*[:.]?\s*\+?\d'}
def pesel_ok(s):
    w=[1,3,7,9,1,3,7,9,1,3]; c=(10-sum(int(a)*b for a,b in zip(s,w))%10)%10; m=int(s[2:4])%20; d=int(s[4:6]); return c==int(s[10]) and 1<=m<=12 and 1<=d<=31
def skan(t):
    t=UUID.sub(' ',t); h={}
    for k,rx in RX.items():
        m=[x.group(0) for x in re.finditer(rx,t)]
        if k=='pesel': m=[x for x in m if pesel_ok(x)]
        if m: h[k]=len(m)
    return h
traf={}; npl=0
for p in sorted(glob.glob(os.path.join(A.dane,'*.json'))+glob.glob(os.path.join(A.strona,'*.html'))):
    npl+=1; h=skan(open(p,encoding='utf-8').read())
    if h: traf[p]=h
if ST:
    okna=' \n'.join(o for r in ST['rekordy'] for s in ((r.get('_dowody') or {}).get('sub') or {}).values() for o in s.get('okna',[])); h=skan(okna)
    if h: traf['stan:_dowody.okna']=h
traf.update(dod)
wynik('skan_danych_osobowych',not traf,plikow=npl,trafienia=traf)
def pliki_repo():
    try: return [f for f in subprocess.run(['git','-C',A.repo,'ls-files','-co','--exclude-standard'],capture_output=True,text=True,check=True).stdout.split('\n') if f]
    except Exception: return None
PLIKI=pliki_repo()
def skanuj_repo(dopasuj):
    """dopasuj(tekst)->lista trafień; skanuje nazwy i treść plików śledzonych/nowych (bez .enc), część jawną buildu."""
    h={}
    for f in PLIKI or []:
        m=dopasuj(f)
        if m: h['nazwa:'+f]=m
        p=os.path.join(A.repo,f)
        if not os.path.isfile(p) or f.endswith('.enc'): continue
        m=dopasuj(open(p,encoding='utf-8',errors='ignore').read())
        if m: h[f]=m
    if A.build:
        for p in glob.glob(os.path.join(A.build,'**','*'),recursive=True)+glob.glob(os.path.join(A.build,'.*')):
            if os.path.isfile(p):
                m=dopasuj(os.path.relpath(p,A.build)+('' if p.endswith('.enc') else '\n'+open(p,encoding='utf-8',errors='ignore').read()))
                if m: h['build:'+os.path.relpath(p,A.build)]=m
    return h
def skanuj_historie(dopasuj):
    """Komunikaty, autorzy i treść wszystkich obiektów w historii (git rev-list --all --objects)."""
    h={}
    try:
        gl=subprocess.run(['git','-C',A.repo,'log','--all','--format=%an%n%ae%n%B'],capture_output=True,text=True).stdout
        m=dopasuj(gl)
        if m: h['komunikaty_commitow']=m
        ob=subprocess.run(['git','-C',A.repo,'rev-list','--all','--objects'],capture_output=True,text=True).stdout.split('\n')
        for ln in ob:
            if ' ' not in ln: continue
            sha,nazwa=ln.split(' ',1)
            if nazwa.endswith('.enc'): continue
            t=subprocess.run(['git','-C',A.repo,'cat-file','-p',sha],capture_output=True).stdout.decode('utf-8','ignore')
            m=dopasuj(nazwa+'\n'+t)
            if m: h.setdefault(nazwa,sorted(set(m)))
    except Exception as e: h['blad']=type(e).__name__
    return h
if PLIKI is None: wynik('lista_plikow_repo',False,powod='brak git ls-files')
# 4. nazwy wykluczone – lista wyłącznie lokalna, poza repo
pw=os.environ.get('PLIK_WYKLUCZEN') or os.path.join(os.path.abspath(A.repo),'..','lokalne','nazwy_wykluczone.txt')
WY=[x.strip().lower() for x in open(pw,encoding='utf-8').read().splitlines() if x.strip()] if os.path.isfile(pw) else []
if WY and PLIKI and any(os.path.abspath(os.path.join(A.repo,f))==os.path.abspath(pw) for f in PLIKI): wynik('brak_nazwy_klienta',False,powod='plik listy wykluczeń jest w repo')
elif not WY: wynik('brak_nazwy_klienta','POMINIETO',powod='brak lokalnej listy nazw wykluczonych (oczekiwane w CI) – podpunkt pominięty; neutralność sprawdza test neutralnosc_repo')
else:
    dw=lambda t:[x for x in WY if x in t.lower()]
    h=skanuj_repo(dw); hh=skanuj_historie(dw)
    if hh: h['historia_git']=hh
    wynik('brak_nazwy_klienta',not h,slow=len(WY),plikow_repo=len(PLIKI or []),trafienia={k:len(v) for k,v in h.items()})
# 4b. neutralność jawnej części repo: słowa tematyczne i nazwy z listy terminów (wzorce z pakietu, terminy ze stanu)
if not ZK: wynik('neutralnosc_repo',False,powod='brak testy/zakazane.json – najpierw: python3 narzedzia/pakiet.py otworz')
else:
    RXZ=re.compile('|'.join(ZK['wzorce']),re.I)
    TER=sorted(TD.terminy(ST,ZK.get('min_dlugosc_terminu',5)) if (ST and TD and ZK.get('terminy_ze_stanu')) else [],key=len,reverse=True)
    RXT=re.compile(r'(?<![a-z0-9])(?:'+'|'.join(re.escape(t) for t in TER)+r')',re.I) if TER else None
    def dz(t):
        m=[x.group(0).lower() for x in RXZ.finditer(t)]+([x.group(0).lower() for x in RXT.finditer(t)] if RXT else [])
        return m
    h=skanuj_repo(dz); hh=skanuj_historie(dz)
    if ST and not TER: h['brak_terminow_ze_stanu']=['?']
    wynik('neutralnosc_repo',not h,plikow_repo=len(PLIKI or []),wzorcow=len(ZK['wzorce']),terminow=len(TER),trafien=sum(len(v) for v in h.values()),trafienia={k:sorted(set(v))[:8] for k,v in h.items()})
    # historia: ostrzeżenie (nie blokuje) – usunięcie wymaga przepisania historii za zgodą właściciela
    wynik('neutralnosc_historii_git','PASS' if not hh else 'OSTRZEZENIE',obiektow_z_trafieniami=len(hh),przyklady=dict(list({k:v[:3] for k,v in hh.items()}.items())[:5]))
# 5–6. noindex i neutralna część jawna buildu
if A.build:
    jaw=[p for p in glob.glob(os.path.join(A.build,'**','*'),recursive=True)+glob.glob(os.path.join(A.build,'.*')) if os.path.isfile(p) and not p.endswith('.enc')]
    ix=open(os.path.join(A.build,'index.html'),encoding='utf-8').read(); rb=open(os.path.join(A.build,'robots.txt')).read() if os.path.exists(os.path.join(A.build,'robots.txt')) else ''
    ni={'meta_noindex_index':bool(re.search(r'<meta name="robots" content="noindex',ix)),'robots_disallow_all':bool(re.search(r'(?m)^Disallow:\s*/\s*$',rb)),
        'meta_noindex_aplikacja_zrodlo':bool(re.search(r'<meta name="robots" content="noindex',open(os.path.join(A.strona,'aplikacja.html'),encoding='utf-8').read()))}
    wynik('noindex',all(ni.values()),**ni)
    ZAK=re.compile('|'.join(ZK['wzorce']),re.I) if ZK else None; h={}
    for p in jaw:
        m=[x.group(0) for x in ZAK.finditer(open(p,encoding='utf-8',errors='ignore').read())] if ZAK else ['brak wzorców']
        if m: h[os.path.relpath(p,A.build)]=sorted(set(m))[:10]
    t=re.search(r'<title>(.*?)</title>',ix); mf=json.load(open(os.path.join(A.build,'manifest.webmanifest')))
    encs=glob.glob(os.path.join(A.build,'dane','*.enc')); zle=[p for p in encs if not enc_ok(p)]
    jawne_dane=[os.path.relpath(p,A.build) for p in jaw if p.endswith('.json') and not p.endswith('klucz.json')]
    neutral=not h and t and t.group(1)=='Przegląd ogłoszeń' and mf.get('name')=='Przegląd ogłoszeń' and not zle and not jawne_dane
    wynik('neutralna_czesc_jawna',bool(neutral),plikow_jawnych=len(jaw),plikow_zaszyfrowanych=len(encs),tytul=t.group(1) if t else None,manifest=mf.get('name'),zakazane_slowa=h,zle_enc=len(zle),jawne_pliki_danych=jawne_dane)
    if os.environ.get('SITE_PASSWORD'):
        p=subprocess.run(['node',os.path.join(A.repo,'narzedzia','sprawdz_build.mjs'),A.build,A.dane],capture_output=True,text=True)
        wynik('odszyfrowanie_buildu',p.returncode==0,wyjscie=(p.stdout or p.stderr).strip()[:400])
# 7. rozmycie tła: włączone domyślnie, wyłączane tylko przez @supports (brak obsługi) lub prefers-reduced-transparency
def css_blokow(css):
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S); stos=[]; buf=''; dekl=[]
    for ch in css:
        if ch=='{': stos.append(buf.strip()); buf=''
        elif ch=='}':
            if buf.strip(): dekl.append((list(stos),buf.strip()))
            stos.pop() if stos else None; buf=''
        elif ch==';' and stos: dekl.append((list(stos),buf.strip())); buf=''
        else: buf+=ch
    return dekl
bl=collections.Counter()
for f in ('aplikacja.html','bramka.html'):
    html=open(os.path.join(A.strona,f),encoding='utf-8').read(); css=' '.join(re.findall(r'<style[^>]*>(.*?)</style>',html,re.S))
    for stos,d in css_blokow(css):
        m=re.match(r'(-webkit-)?backdrop-filter\s*:\s*(.+)',d.split('{')[-1].strip())
        if not m: continue
        v=m.group(2).strip(); at=' '.join(s for s in stos if s.startswith('@'))
        if v.startswith('none'):
            bl['wylaczenia']+=1
            if 'prefers-reduced-transparency' not in at and not re.search(r'@supports\s+not',at): bl[f'wylaczenie_poza_dozwolonym:{f}']+=1
        else:
            bl['wlaczenia']+=1
            if '@supports' not in at and 'prefers-reduced-transparency' not in at: bl['wlaczenie_bez_supports']+=1
    if re.search(r'backdrop-filter\s*:\s*none\s*!important',css): bl[f'na_stale:{f}']+=1
    if re.search(r"style\.(webkitB|b)ackdropFilter\s*=|classList\.add\(['\"](no-?blur|bez-?rozmycia)",html): bl[f'wylaczenie_w_js:{f}']+=1
okb=bl['wlaczenia']>=2 and not [k for k in bl if ':' in k or k=='wlaczenie_bez_supports']
wynik('rozmycie_tla',okb,**dict(bl))
if A.wynik: json.dump(W,open(A.wynik,'w'),ensure_ascii=False,indent=1)
zle=[w['test'] for w in W if w['wynik']=='FAIL']; pom=[w['test'] for w in W if w['wynik'] not in ('PASS','FAIL')]; print('WYNIK:', ('PASS' if not zle else 'FAIL '+', '.join(zle))+(f' (pominięte/ostrzeżenia: {", ".join(pom)})' if pom else '')); sys.exit(1 if zle else 0)
