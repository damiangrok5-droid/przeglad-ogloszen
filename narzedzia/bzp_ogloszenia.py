"""Ogłoszenia BZP towarzyszące postępowaniu: o wyniku (TenderResultNotice), o zamiarze zawarcia umowy (AgreementIntentionNotice)
i o zmianie ogłoszenia (NoticeUpdateNotice). Parsowanie treści z API e-Zamówień (treść nie jest przechowywana),
dopasowanie zmian do znanych postępowań i pola pochodne rekordu (wykonawcy, wartości, terminy po zmianie) ze źródłem."""
import re, datetime
from zoneinfo import ZoneInfo
import szczegoly as S
from wspolne import wykonawca_wyniku
PL=ZoneInfo('Europe/Warsaw'); UTC=datetime.timezone.utc
TYPY_CPV=["ContractNotice","TenderResultNotice","AgreementIntentionNotice"]   # z filtrem CPV 336
TYP_ZMIANA="NoticeUpdateNotice"                                                 # bez CPV w API – dopasowanie do znanych rekordów
NAZWY={'ContractNotice':'ogłoszenie o zamówieniu','TenderResultNotice':'ogłoszenie o wyniku postępowania','AgreementIntentionNotice':'ogłoszenie o zamiarze zawarcia umowy','NoticeUpdateNotice':'ogłoszenie o zmianie ogłoszenia'}
def link(obj): return f"https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{obj}"
def nr_bazowy(n): m=re.search(r'(\d{4}/BZP\s*\d{6,9})',n or ''); return re.sub(r'\s+',' ',m.group(1)) if m else None
def kwota(s):
    m=re.search(r'(\d[\d\s.]*(?:,\d{1,2})?)\s*([A-Z]{3})\b',s or '')
    if not m: return None,None
    v=m.group(1).replace(' ','').replace('\xa0','')
    if ',' in v: v=v.replace('.','').replace(',','.')
    try: return round(float(v),2),m.group(2)
    except ValueError: return None,None
CZ=re.compile(r'(?:^|\s)Część\s+(\d+)\s*$')
def wynik(x):
    """TenderResultNotice -> {'wyniki':[{czesc,rozstrzygniecie,wykonawca,wartosc,waluta,data_umowy}], 'opis'}"""
    L=S.bzp_linie(x.get('htmlBody')); i0=next((i for i,l in enumerate(L) if l.startswith('SEKCJA V')),None)
    out=[]; cur=None
    if i0 is None: return {'wyniki':[],'opis':None}
    def nowy(c): return {'czesc':c,'rozstrzygniecie':None,'wykonawca':[],'wartosc':None,'waluta':None,'cena_oferty':None,'data_umowy':None}
    for l in L[i0:]:
        m=CZ.search(l)
        if m: cur=nowy(int(m.group(1))); out.append(cur); continue
        if cur is None: cur=nowy(None); out.append(cur)
        if l.startswith('5.1.)'): cur['rozstrzygniecie']='unieważnienie' if 'unieważnieniem' in l.split(':')[-1] else ('zawarcie umowy' if 'zawarciem umowy' in l.split(':')[-1] else None)
        elif re.match(r'7\.\d+\.\d+\)\s*Nazwa \(firma\) wykonawcy',l): n=wykonawca_wyniku(l.split(':',1)[1].strip().rstrip(',').strip()); n and n!='brak danych' and cur['wykonawca'].append(n)
        elif l.startswith('8.2.)'): cur['wartosc'],cur['waluta']=kwota(l.split(':',1)[1])
        elif l.startswith('6.4.)'): cur['cena_oferty']=kwota(l.split(':',1)[1])[0]
        elif l.startswith('8.1.)'): m2=re.search(r'\d{4}-\d{2}-\d{2}',l); cur['data_umowy']=m2.group(0) if m2 else None
    out=[w for w in out if w['rozstrzygniecie'] or w['wykonawca'] or w['wartosc'] is not None]
    for w in out:
        if w['wartosc'] is None and w['cena_oferty'] is not None: w['wartosc']=w['cena_oferty']; w['wartosc_zrodlo']='6.4 cena oferty wybranej'
        elif w['wartosc'] is not None: w['wartosc_zrodlo']='8.2 wartość umowy'
        w.pop('cena_oferty',None)
    zaw=sum(1 for w in out if w['rozstrzygniecie']=='zawarcie umowy'); un=sum(1 for w in out if w['rozstrzygniecie']=='unieważnienie')
    opis='wynik: '+', '.join(p for p in ([f'zawarcie umowy ({zaw} cz.)' if len(out)>1 else 'zawarcie umowy'] if zaw else [])+([f'unieważnienie ({un} cz.)' if len(out)>1 else 'unieważnienie'] if un else []))
    return {'wyniki':out,'opis':opis if (zaw or un) else 'wynik: brak w ogłoszeniu'}
CZAS=re.compile(r'(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?')
def zmiana(x):
    """NoticeUpdateNotice -> {'zmieniane':numer BZP, 'zmiany':[{miejsce,przed,po}], 'opis'}"""
    L=S.bzp_linie(x.get('htmlBody')); t='\n'.join(L)
    m=re.search(r'Numer zmienianego ogłoszenia w BZP:\s*(\d{4}/BZP\s*\d+)',t); zm=nr_bazowy(m.group(1)) if m else None
    m=re.search(r'Nazwa zmienianego ogłoszenia:\s*(.*?)\s*\d\.\d\.\)',t,re.S); rodz=re.sub(r'\s+',' ',m.group(1)).strip()[:80] if m else None
    zmiany=[]
    for blok in re.split(r'\d\.\d\.\d\.\)\s*Opis zmiany, w tym tekst, który należy dodać lub zmienić:',t)[1:]:
        b=re.split(r'\n\d{4}-\d{2}-\d{2} Biuletyn Zamówień Publicznych',blok)[0]
        mp=re.search(r'^(.*?)Przed zmianą:\s*(.*?)\s*Po zmianie:\s*(.*)$',b,re.S)
        if mp: miejsce,przed,po=(re.sub(r'\s+',' ',g).strip() for g in mp.groups())
        else: miejsce,przed,po='',None,re.sub(r'\s+',' ',b).strip()
        miejsce=re.sub(r'^SEKCJA [IVX]+\s*[-–]?\s*\w*\s*','',miejsce).strip()
        zmiany.append({'miejsce':S.cut(S.czysc(miejsce),120),'przed':S.cut(S.czysc(przed),200) if przed else None,'po':S.cut(S.czysc(po),200)})
    kr=[]
    for z in zmiany:
        if z['przed'] is not None and len(z['przed'])<=40 and len(z['po'])<=40: kr.append(f"{z['miejsce'] or 'zmiana'}: {z['przed']} → {z['po']}")
        else: kr.append(z['miejsce'] or 'zmiana treści')
    pre='zmiana'+(f' ({rodz[0].lower()+rodz[1:]})' if rodz else '')+': '
    opis=pre+('; '.join(kr) if kr else 'brak opisu w ogłoszeniu')
    return {'zmieniane':zm,'zmieniane_rodzaj':rodz,'zmiany':zmiany,'opis':S.cut(opis,400)}
RODZ_OK=re.compile(r'o zamówieniu|o wyniku postępowania|o zamiarze zawarcia umowy',re.I)
def zamiar(x): return {'opis':'zamiar zawarcia umowy'}
def opisz(x):
    t=x.get('noticeType')
    if t=='TenderResultNotice': return wynik(x)
    if t==TYP_ZMIANA: return zmiana(x)
    if t=='AgreementIntentionNotice': return zamiar(x)
    return {}
# ---------- dopasowanie zmian ----------
def klucz_tekst(s): return re.sub(r'[^0-9a-ząćęłńóśźż]+',' ',(s or '').casefold()).strip()
def tytul(x):
    L=S.bzp_linie(x.get('htmlBody'))
    return (x.get('orderObject') or (L[2] if len(L)>2 and not L[2].startswith('SEKCJA') else '')).strip()
class Indeks:
    """Indeks znanych postępowań BZP: tenderId, numer ogłoszenia (bez wersji), (przedmiot, zamawiający)."""
    def __init__(s,rekordy):
        s.tid={}; s.nr={}; s.tekst={}
        for r in rekordy: s.dodaj(r)
    def dodaj(s,r):
        if r.get('zrodlo')!='BZP': return
        s.tid[r['id'][4:]]=r['id']
        for n in [r.get('numer')]+[h.get('numer') for h in r.get('historia') or []]:
            b=nr_bazowy(n)
            if b: s.nr[b]=r['id']
        k=(klucz_tekst(r.get('przedmiot')),klucz_tekst(r.get('zamawiajacy')))
        if len(k[0])>=12: s.tekst.setdefault(k,set()).add(r['id'])
    def dopasuj(s,x,info=None):
        """-> (rid, metoda) albo (None,None). Kolejność: identyfikator postępowania, numer zmienianego ogłoszenia, przedmiot+zamawiający (jednoznacznie)."""
        if x.get('tenderId') in s.tid: return s.tid[x['tenderId']],'identyfikator postępowania'
        info=info if info is not None else zmiana(x)
        if info.get('zmieniane') in s.nr: return s.nr[info['zmieniane']],'numer zmienianego ogłoszenia'
        if not RODZ_OK.search(info.get('zmieniane_rodzaj') or ''): return None,None   # np. zmiany ogłoszeń o wykonaniu umowy – tylko po identyfikatorze/numerze
        c=s.tekst.get((klucz_tekst(tytul(x)),klucz_tekst(x.get('organizationName'))))
        if c and len(c)==1: return next(iter(c)),'przedmiot i zamawiający'
        return None,None
# ---------- pola pochodne rekordu ----------
def _utc(d,hm):
    try: return datetime.datetime.fromisoformat(f'{d}T{hm or "00:00"}').replace(tzinfo=PL).astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError: return None
def pochodne(r):
    """Uzupełnia rekord BZP z historii: wyniki_bzp (wykonawca, wartość, część, źródło), wartosc_calkowita (gdy jedno źródło),
    termin po zmianie ogłoszenia (termin_ofert + pola szczegółów ze źródłem). Idempotentne."""
    if r.get('zrodlo')!='BZP': return
    H=sorted(r.get('historia') or [],key=lambda h:(h.get('data') or '',h.get('numer') or ''))
    wyn=[]
    for h in H:
        for w in h.get('wyniki') or []:
            wyn.append({**w,'numer':h['numer'],'link':h['link'],'data':h.get('data')})
    # ostatnie ogłoszenie o wyniku dla danej części wygrywa (sprostowania/kolejne wyniki)
    ost={}
    for w in wyn: ost[(w['czesc'])]=w
    if any(k is not None for k in ost) and None in ost: del ost[None]   # wynik bez podziału zastąpiony wynikami części
    if not ost: r.pop('wyniki_bzp',None)
    else: r['wyniki_bzp']=sorted(ost.values(),key=lambda w:(w['czesc'] is None,w['czesc'] or 0))
    if r.get('wyniki_bzp'):
        wal={w['waluta'] for w in r['wyniki_bzp'] if w['wartosc'] is not None}; zrn=sorted({w['numer'] for w in r['wyniki_bzp'] if w['wartosc'] is not None})
        vs=[w['wartosc'] for w in r['wyniki_bzp'] if w['wartosc'] is not None]
        if vs and len(wal)==1:
            r['wartosc_calkowita']=round(sum(vs),2); r['wartosc_calkowita_waluta']=next(iter(wal))
            r['wartosc_calkowita_zrodlo']={'opis':('suma wartości umów z ogłoszeń o wyniku (części: %d)'%len(vs)) if len(vs)>1 else 'wartość umowy z ogłoszenia o wyniku',
                                           'ogloszenia':[[n,next(w['link'] for w in r['wyniki_bzp'] if w['numer']==n)] for n in zrn]}
    # zmiany terminów
    zm=[(h,z) for h in H if h.get('typ')==TYP_ZMIANA for z in h.get('zmiany') or []]
    sz=(r.get('szczegoly') or {}).get('pola') or {}
    for pole_sz,wz in (('termin_ofert',r'termin składania ofert'),('otwarcie_ofert',r'termin otwarcia ofert')):
        traf=[(h,z) for h,z in zm if re.search(wz,z['miejsce'] or '',re.I) and CZAS.search(z['po'] or '')]
        if not traf: continue
        h,z=traf[-1]; m=CZAS.search(z['po']); nowa=m.group(1)+(' '+m.group(2) if m.group(2) else '')
        if pole_sz=='termin_ofert' and m.group(2):
            u=_utc(m.group(1),m.group(2))
            if u and h.get('data','')>=str(r.get('data_publikacji') or ''): r.setdefault('termin_ofert_pierwotny',(_utc(*CZAS.search(z['przed']).groups()) if z.get('przed') and CZAS.search(z['przed']) else None) or r.get('termin_ofert')); r['termin_ofert']=u; r['termin_ofert_zrodlo']={'numer':h['numer'],'link':h['link']}
        p=sz.get(pole_sz)
        if p is not None:
            p.setdefault('w0',p['w']); p.setdefault('z0',p['z'])
            p['w']=f"{nowa} (po zmianie; wcześniej: {z['przed']})" if z.get('przed') else f"{nowa} (po zmianie)"
            p['z']=f"ogłoszenie o zmianie {h['numer']}: sekcja III, „Po zmianie”"; p['zm']=[h['numer'],h['link']]
