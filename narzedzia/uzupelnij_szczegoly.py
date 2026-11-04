"""Uzupełnia rekordy o pola szczegółowe z ogłoszeń (narzedzia/szczegoly.py).
Źródła: TED API v3 (zapytanie po numerach publikacji, pauza 1,5 s) i API tablicy BZP (≤30 zapytań/min, pauza 3 s, robots.txt).
Nie pobiera niczego z platform zakupowych – adresy platform są tylko przepisywane z ogłoszeń.
Użycie (uzupełnienie wsteczne): python3 narzedzia/uzupelnij_szczegoly.py --stan stan/stan.json.gz [--strona strona/dane] [--wszystkie] [--suchy]"""
import os, sys, json, gzip, datetime, collections, urllib.parse
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from zoneinfo import ZoneInfo
import szczegoly as S
import reguly as RG
from zrodla import Zrodlo, Blokada, ted_szukaj, bzp_okres, bzp_page_size, BZP_API
PL=ZoneInfo('Europe/Warsaw')
def potrzebne(R,wszystkie=False):
    out=[]
    for r in R:
        h=S.wybierz_ogloszenie(r)
        if not h: continue
        sz=r.get('szczegoly') or {}
        if wszystkie or (sz.get('ogloszenie') or {}).get('numer')!=h['numer']: out.append((r,h))
    return out
def _ogl(h,zr): return {'numer':h['numer'],'typ':h.get('typ'),'data':h.get('data'),'link':h['link'],'zrodlo':zr}
def uzupelnij(R,log=print,bzp_wiersze=None,bzp_miesiace=False,max_bzp_pojedyncze=120,wszystkie=False,ps=None):
    """R: lista rekordów (modyfikowana w miejscu). bzp_wiersze: {objectId: ogłoszenie z htmlBody} pobrane już w tym przebiegu."""
    W={'ted':0,'bzp':0,'nieznalezione':[],'bledy':[],'zrodla':{}}; pobrano=datetime.datetime.now(PL).isoformat(timespec='seconds')
    P=potrzebne(R,wszystkie); T=[(r,h) for r,h in P if r['zrodlo']=='TED']; B=[(r,h) for r,h in P if r['zrodlo']=='BZP']
    log(f'szczegóły: do uzupełnienia TED {len(T)}, BZP {len(B)}')
    if T:
        z=Zrodlo('TED','api.ted.europa.eu',1.5,log=log); N={}
        nums=sorted({h['numer'] for _,h in T})
        try:
            for i in range(0,len(nums),100):
                ns,_=ted_szukaj(z,'publication-number IN ('+' '.join(nums[i:i+100])+')',S.TED_POLA_SZCZ,limit=100)
                for n in ns: N[n['publication-number']]=n
                if (i//100)%10==9: log(f'szczegóły TED: {i+100}/{len(nums)}')
        except (Blokada,RuntimeError) as e: W['bledy'].append('TED: '+str(e)); log('szczegóły TED STOP: '+str(e))
        for r,h in T:
            n=N.get(h['numer'])
            if n is None: W['nieznalezione'].append(h['numer']); continue
            r['szczegoly']=S.opakuj(S.z_ted(n),'TED',_ogl(h,'TED'),pobrano); W['ted']+=1
            r['plik_skladu']=RG.wsk_opakuj(RG.wsk_ted(n),h,pobrano[:10])
        W['zrodla']['TED']=z.podsumowanie()
    if B:
        z=Zrodlo('BZP','ezamowienia.gov.pl',3.0,limit_min=30,log=log); X=dict(bzp_wiersze or {}); ps=ps or bzp_page_size()
        oid=lambda h:h['link'].rsplit('/',1)[-1]
        try:
            if bzp_miesiace:
                mies=collections.defaultdict(set)
                for r,h in B:
                    if oid(h) not in X: mies[('ContractNotice' if h.get('typ')=='ContractNotice' else 'TenderResultNotice',(h.get('data') or '')[:7])].add(oid(h))
                for (typ,m),ids in sorted(mies.items(),key=lambda k:(k[0][1],k[0][0])):
                    if not m: continue
                    a=datetime.date.fromisoformat(m+'-01'); b=(a.replace(day=28)+datetime.timedelta(days=4)).replace(day=1)-datetime.timedelta(days=1)
                    xs,luka,_=bzp_okres(z,typ,a,b,ps)
                    for x in xs:
                        if x.get('objectId') in ids: X[x['objectId']]=x
                    if luka: W['bledy'].append(f'BZP luka {luka}')
                    log(f'szczegóły BZP {typ} {m}: znaleziono {len(ids & set(X))}/{len(ids)}, zapytań {len(z.zapytania)}')
            braki=[(r,h) for r,h in B if oid(h) not in X][:max_bzp_pojedyncze]
            for r,h in braki:   # pojedyncze ogłoszenie po numerze (1 zapytanie)
                d=h.get('data') or ''
                if not d: continue
                p={'NoticeType':h.get('typ') or 'ContractNotice','NoticeNumber':h['numer'],'PublicationDateFrom':f'{d}T00:00:00','PublicationDateTo':f'{d}T23:59:59','PageSize':10}
                for x in z.zapytaj(BZP_API+'?'+urllib.parse.urlencode(p)) or []:
                    if x.get('objectId')==oid(h): X[x['objectId']]=x
        except Blokada as e: W['bledy'].append('BZP: '+str(e)); log('szczegóły BZP STOP: '+str(e))
        for r,h in B:
            x=X.get(oid(h))
            if x is None or not x.get('htmlBody'): W['nieznalezione'].append(h['numer']); continue
            r['szczegoly']=S.opakuj(S.z_bzp(x),'BZP',_ogl(h,'BZP'),pobrano); W['bzp']+=1
            r['plik_skladu']=RG.wsk_opakuj(RG.wsk_bzp(x),h,pobrano[:10])
        W['zrodla']['BZP']=z.podsumowanie()
    log(f"szczegóły: uzupełniono TED {W['ted']}, BZP {W['bzp']}, nieznalezione {len(W['nieznalezione'])}, błędy {len(W['bledy'])}")
    return W
def uzupelnij_wskazowki(R,log=print,max_bzp=25):
    """Wskazanie „który plik pobrać” dla otwartych postępowań, które jeszcze go nie mają (pozostałe dostają je razem z polami szczegółowymi).
    TED: zapytania zbiorcze po 100 numerów (tylko pola opisu); BZP: najwyżej max_bzp pojedynczych zapytań na przebieg (limit 30/min)."""
    W={'ted':0,'bzp':0,'bledy':[]}; dz=datetime.datetime.now(PL).date().isoformat()
    P=[(r,S.wybierz_ogloszenie(r)) for r in R if r.get('status')=='otwarte' and 'plik_skladu' not in r and r.get('historia')]
    P=[(r,h) for r,h in P if h and h.get('numer') and h.get('link')]
    T=[(r,h) for r,h in P if r['zrodlo']=='TED']; B=[(r,h) for r,h in P if r['zrodlo']=='BZP'][:max_bzp]
    log(f'wskazówki plików: TED {len(T)}, BZP {len(B)}')
    if T:
        z=Zrodlo('TED','api.ted.europa.eu',1.5,log=log); N={}; nums=sorted({h['numer'] for _,h in T})
        try:
            for i in range(0,len(nums),100):
                ns,_=ted_szukaj(z,'publication-number IN ('+' '.join(nums[i:i+100])+')',['publication-number']+RG.POLA_WSK_TED,limit=100)
                for n in ns: N[n['publication-number']]=n
        except (Blokada,RuntimeError) as e: W['bledy'].append('TED: '+str(e))
        for r,h in T:
            if h['numer'] in N: r['plik_skladu']=RG.wsk_opakuj(RG.wsk_ted(N[h['numer']]),h,dz); W['ted']+=1
    if B:
        z=Zrodlo('BZP','ezamowienia.gov.pl',3.0,limit_min=30,log=log)
        try:
            for r,h in B:
                d=h.get('data') or ''; oid=h['link'].rsplit('/',1)[-1]
                if not d: continue
                p={'NoticeType':h.get('typ') or 'ContractNotice','NoticeNumber':h['numer'],'PublicationDateFrom':f'{d}T00:00:00','PublicationDateTo':f'{d}T23:59:59','PageSize':10}
                x=next((x for x in z.zapytaj(BZP_API+'?'+urllib.parse.urlencode(p)) or [] if x.get('objectId')==oid),None)
                if x and x.get('htmlBody'): r['plik_skladu']=RG.wsk_opakuj(RG.wsk_bzp(x),h,dz); W['bzp']+=1
        except Blokada as e: W['bledy'].append('BZP: '+str(e))
    log(f"wskazówki plików: uzupełniono TED {W['ted']}, BZP {W['bzp']}, błędy {len(W['bledy'])}")
    return W
if __name__=='__main__':
    import argparse; ap=argparse.ArgumentParser(); ap.add_argument('--stan',required=True); ap.add_argument('--strona'); ap.add_argument('--wszystkie',action='store_true')
    ap.add_argument('--suchy',action='store_true'); ap.add_argument('--tylko',choices=['TED','BZP']); A=ap.parse_args()
    op=gzip.open if A.stan.endswith('.gz') else open
    ST=json.load(op(A.stan,'rt',encoding='utf-8'))
    R=[r for r in ST['rekordy'] if not A.tylko or r['zrodlo']==A.tylko]
    W=uzupelnij(R,bzp_miesiace=True,max_bzp_pojedyncze=400,wszystkie=A.wszystkie)
    json.dump(W,open('/tmp/uzupelnij_wynik.json','w'),ensure_ascii=False,indent=1)
    if not A.suchy:
        with op(A.stan+'.tmp','wt',encoding='utf-8') as f: json.dump(ST,f,ensure_ascii=False)
        os.replace(A.stan+'.tmp',A.stan)
        if A.strona:
            from eksport import eksport; print(eksport(ST,A.strona))
