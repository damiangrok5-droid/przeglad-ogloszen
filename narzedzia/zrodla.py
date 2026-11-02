"""Klienci źródeł z limitami i robots.txt.
- TED Search API v3 (POST /v3/notices/search): pauza 1,5 s; przy 403/odpowiedzi HTML (wyzwanie WAF) – STOP bez ponawiania i bez obchodzenia.
- BZP (e-Zamówienia, mo-board/api/v1/notice): najwyżej 30 zapytań na minutę (pauza 3 s + kontrola okna 60 s);
  od 2027-01-11 strona = 100 rekordów (BZP_PAGE_SIZE nadpisuje); stronicowanie SearchAfter do pustej/niepełnej strony.
- robots.txt: sprawdzany przed pierwszym zapytaniem do hosta; Disallow -> STOP; Crawl-delay podnosi pauzę; robots.txt niedostępny (5xx/błąd sieci) -> STOP (RFC 9309).
- Endpointy e-Zamówień traktowane jako niestabilne: błędy i luki są logowane, przebieg kończy się kodem błędu zamiast cichego pominięcia."""
import json, time, urllib.request, urllib.error, urllib.parse, urllib.robotparser, datetime, re, html, collections, os
UA='przeglad-ogloszen/1.0 (+aktualizacja dwa razy w tygodniu)'
class Blokada(Exception): pass
class Zrodlo:
    def __init__(s,nazwa,host,pauza,limit_min=None,log=None):
        s.nazwa,s.host,s.pauza,s.limit_min,s.log=nazwa,host,pauza,limit_min,log or (lambda *a:None)
        s.zapytania=[]; s.kody=collections.Counter(); s.bledy=[]; s.rp=None; s.ostatnie=0
    def robots(s,sciezka):
        if s.rp is None:
            u=f'https://{s.host}/robots.txt'; rp=urllib.robotparser.RobotFileParser()
            try:
                r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':UA}),timeout=30); rp.parse(r.read().decode('utf-8','replace').splitlines()); s.robots_stan=f'{u}: HTTP {r.status}'
            except urllib.error.HTTPError as e:
                if 400<=e.code<500: rp.parse([]); s.robots_stan=f'{u}: HTTP {e.code} (brak pliku = brak ograniczeń)'
                else: raise Blokada(f'{s.nazwa}: robots.txt niedostępny (HTTP {e.code}) – przerwano zgodnie z RFC 9309')
            except Exception as e: raise Blokada(f'{s.nazwa}: robots.txt niedostępny ({type(e).__name__}) – przerwano')
            s.rp=rp; cd=rp.crawl_delay(UA) or rp.crawl_delay('*')
            if cd and float(cd)>s.pauza: s.pauza=float(cd)
            s.log(f'{s.nazwa}: {s.robots_stan}; crawl-delay={cd}; pauza={s.pauza}s')
        url=f'https://{s.host}{sciezka}'
        if not (s.rp.can_fetch(UA,url) and s.rp.can_fetch('*',url)): raise Blokada(f'{s.nazwa}: robots.txt nie pozwala na {sciezka} – przerwano')
    def czekaj(s):
        w=s.ostatnie+s.pauza-time.time()
        if w>0: time.sleep(w)
        if s.limit_min:
            teraz=time.time(); ost=[t for t in s.zapytania if teraz-t<60]
            if len(ost)>=s.limit_min: time.sleep(60-(teraz-ost[0])+0.1)
    def zapytaj(s,url,dane=None,proby=3):
        p=urllib.parse.urlparse(url); s.robots(p.path)
        for proba in range(proby):
            s.czekaj(); t=time.time(); s.zapytania.append(t); s.ostatnie=t
            try:
                rq=urllib.request.Request(url,data=json.dumps(dane).encode() if dane is not None else None,
                    headers={'User-Agent':UA,'Accept':'application/json',**({'Content-Type':'application/json'} if dane is not None else {})})
                r=urllib.request.urlopen(rq,timeout=180); body=r.read(); s.ostatnie=time.time(); s.kody[r.status]+=1
                if 'json' not in (r.headers.get('Content-Type') or '') and body[:1] not in (b'{',b'['):
                    raise Blokada(f'{s.nazwa}: odpowiedź nie-JSON (możliwe wyzwanie WAF) – przerwano bez ponawiania')
                return json.loads(body)
            except urllib.error.HTTPError as e:
                s.ostatnie=time.time(); s.kody[e.code]+=1; s.bledy.append(f'HTTP {e.code} {p.path}')
                if e.code==403: raise Blokada(f'{s.nazwa}: HTTP 403 (blokada) – przerwano bez obchodzenia')
                if e.code==429:
                    ra=e.headers.get('Retry-After'); w=min(float(ra) if ra and ra.isdigit() else 65,300); s.log(f'{s.nazwa}: 429, czekam {w}s'); time.sleep(w); continue
                time.sleep(15*(proba+1))
            except Blokada: raise
            except Exception as e:
                s.ostatnie=time.time(); s.kody['błąd:'+type(e).__name__]+=1; s.bledy.append(f'{type(e).__name__} {p.path}'); time.sleep(15*(proba+1))
        return None
    def podsumowanie(s): return {'zapytan':len(s.zapytania),'kody':{str(k):v for k,v in s.kody.items()},'bledy':s.bledy[-20:],'pauza_s':s.pauza,'robots':getattr(s,'robots_stan',None),
        'max_na_minute':max((sum(1 for u in s.zapytania if 0<=u-t<60) for t in s.zapytania),default=0)}
# ---------------- TED ----------------
TED_API='https://api.ted.europa.eu/v3/notices/search'
TED_POLA=["publication-number","publication-date","notice-type","procedure-identifier","procedure-type","buyer-name","buyer-city","notice-title",
   "title-lot","description-lot","identifier-lot","estimated-value-lot","estimated-value-cur-lot","winner-name","result-lot-identifier",
   "deadline-receipt-tender-date-lot","total-value","total-value-cur","place-of-performance","title-proc","description-proc","additional-information-lot","classification-cpv"]
def ted_zapytanie(terms,od):
    return "("+" OR ".join("FT~"+(t if (t.startswith('"') or '*' in t) else f'"{t}"') for t in terms)+f") AND buyer-country=POL AND publication-date>={od}"
def ted_szukaj(z,query,pola=TED_POLA,limit=250):
    out=[]; page=1
    while True:
        d=z.zapytaj(TED_API,{"query":query,"fields":pola,"limit":limit,"page":page,"scope":"ALL","paginationMode":"PAGE_NUMBER"})
        if d is None: raise RuntimeError('TED: brak odpowiedzi po ponowieniach: '+query[:80])
        ns=d.get('notices',[]); out+=ns
        if len(ns)<limit: return out,d.get('totalNoticeCount')
        page+=1
        if page>40: raise RuntimeError('TED: ponad 10 000 wyników dla jednego zapytania – sprawdź termin')
# ---------------- BZP ----------------
BZP_API='https://ezamowienia.gov.pl/mo-board/api/v1/notice'
BZP_TYPY=["ContractNotice","TenderResultNotice","AgreementIntentionNotice"]   # z CpvCode=336
BZP_TYP_ZMIANA="NoticeUpdateNotice"   # bez CPV w API: pobierane bez filtra CPV i dopasowywane do znanych postępowań
def bzp_page_size(dzis=None):
    if os.environ.get('BZP_PAGE_SIZE'): return int(os.environ['BZP_PAGE_SIZE'])
    return 100 if (dzis or datetime.date.today())>=datetime.date(2027,1,11) else 500
def bzp_tekst(h): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',h or '')))
def bzp_okres(z,typ,od,do,page_size,cpv='336',filtr=None):
    """Wszystkie ogłoszenia typu typ (domyślnie z CPV zawierającym 336; cpv=None = bez filtra CPV) opublikowane w [od, do].
    filtr(x)->bool: zachowuje tylko pasujące (strumieniowo, bez trzymania całej strony w pamięci). Zwraca (lista, luka|None, liczba_stron)."""
    sa=None; out=[]; widziane=set(); strony=0
    while True:
        p={'NoticeType':typ,'PublicationDateFrom':f'{od}T00:00:00','PublicationDateTo':f'{do}T23:59:59','PageSize':page_size}
        if cpv: p['CpvCode']=cpv
        if sa: p['SearchAfter']=sa
        d=z.zapytaj(BZP_API+'?'+urllib.parse.urlencode(p)); strony+=1
        if d is None: return out,[typ,str(od),str(do),sa],strony
        nowe=[x for x in d if x.get('objectId') not in widziane]
        for x in nowe: widziane.add(x['objectId'])
        out+=[x for x in nowe if filtr is None or filtr(x)]
        if not nowe or len(d)<min(page_size,100): return out,None,strony   # niepełna strona = koniec (odporne na limit 100 po stronie serwera)
        sa=d[-1]['objectId']
