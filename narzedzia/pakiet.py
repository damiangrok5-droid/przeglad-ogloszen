"""Zaszyfrowany pakiet plików roboczych (treść merytoryczna, reguły, interfejs po odszyfrowaniu).
W repo jest tylko pakiet/pakiet.enc; rozpakowane pliki są w .gitignore.
Szyfrowanie: narzedzia/stan.mjs (AES-256-GCM, PBKDF2-SHA256 600 000 iteracji, hasło z SITE_PASSWORD).
Użycie: python3 narzedzia/pakiet.py zamknij   – pakuje pliki z listy PLIKI do pakiet/pakiet.enc
        python3 narzedzia/pakiet.py otworz    – odtwarza pliki z pakiet/pakiet.enc
        python3 narzedzia/pakiet.py sprawdz   – porównuje pakiet z plikami na dysku (kod 1 przy różnicy)"""
import os, sys, json, gzip, base64, hashlib, subprocess, tempfile
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLIKI=['narzedzia/aktualizuj.py','narzedzia/zalaczniki.py','testy/test_zalaczniki.py','narzedzia/dowody.py','narzedzia/eksport.py','narzedzia/reguly.py','narzedzia/slownik.py','narzedzia/wspolne.py',
       'strona/aplikacja.html','testy/testy_danych.py','testy/zakazane.json','narzedzia/grupowanie.py','testy/test_grupowanie.py']
ENC=os.path.join(R,'pakiet','pakiet.enc')
def stan(cmd,a,b): subprocess.run(['node',os.path.join(R,'narzedzia','stan.mjs'),cmd,a,b],check=True,stdout=subprocess.DEVNULL)
def zamknij():
    d={p:base64.b64encode(open(os.path.join(R,p),'rb').read()).decode() for p in PLIKI}
    os.makedirs(os.path.dirname(ENC),exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        g=os.path.join(t,'p.json.gz'); gzip.open(g,'wt',encoding='utf-8',compresslevel=9).write(json.dumps({'v':1,'pliki':d},sort_keys=True)); stan('szyfruj',g,ENC)
    print(f'zamknięto {len(d)} plików -> pakiet/pakiet.enc')
def czytaj():
    with tempfile.TemporaryDirectory() as t:
        g=os.path.join(t,'p.json.gz'); stan('odszyfruj',ENC,g); return json.load(gzip.open(g,'rt',encoding='utf-8'))['pliki']
def otworz():
    d=czytaj()
    for p,b in d.items():
        os.makedirs(os.path.dirname(os.path.join(R,p)),exist_ok=True); open(os.path.join(R,p),'wb').write(base64.b64decode(b))
    print(f'otwarto {len(d)} plików')
def sprawdz():
    d=czytaj(); r=[p for p in PLIKI if p not in d or not os.path.exists(os.path.join(R,p)) or open(os.path.join(R,p),'rb').read()!=base64.b64decode(d[p])]
    print(json.dumps({'plikow':len(d),'rozne':r},ensure_ascii=False)); sys.exit(1 if r else 0)
if __name__=='__main__': {'zamknij':zamknij,'otworz':otworz,'sprawdz':sprawdz}[sys.argv[1]]()
