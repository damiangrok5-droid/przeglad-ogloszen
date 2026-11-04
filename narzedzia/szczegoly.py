"""Pola szczegółowe z publicznych ogłoszeń: BZP (treść ogłoszenia z API tablicy e-Zamówień) i TED (pola eForms z API v3).
Każde pole ma wartość albo 'brak w ogłoszeniu' i źródło (numer i link ogłoszenia + sekcja/pole). Nic nie jest zgadywane.
Dane kontaktowe osób (imiona i nazwiska, telefony, imienne e-maile) są pomijane: zapisujemy wyłącznie adresy instytucji."""
import re, html, datetime
from zoneinfo import ZoneInfo
from wspolne import IMIONA
PL=ZoneInfo('Europe/Warsaw')
BRAK='brak w ogłoszeniu'
POLA=['nip_regon','adres','email','www','termin_ofert','otwarcie_ofert','strona_postepowania','skladanie_ofert','numer_referencyjny','okres_umowy','kryteria','czesci']
ETYKIETY={'nip_regon':'NIP/REGON zamawiającego','adres':'Adres zamawiającego','email':'E-mail zamawiającego (ogólny)','www':'Strona internetowa zamawiającego',
 'termin_ofert':'Termin składania ofert','otwarcie_ofert':'Termin otwarcia ofert','strona_postepowania':'Strona postępowania (dokumenty)','skladanie_ofert':'Miejsce składania ofert',
 'numer_referencyjny':'Numer referencyjny','okres_umowy':'Okres realizacji / obowiązywania umowy','kryteria':'Kryteria oceny ofert (waga)','czesci':'Części (pakiety)'}
ZR_BZP={'nip_regon':'sekcja I: Krajowy Numer Identyfikacyjny','adres':'sekcja I: Ulica / Kod pocztowy / Miejscowość','email':'sekcja I: Adres poczty elektronicznej',
 'www':'sekcja I: Adres strony internetowej zamawiającego','termin_ofert':'sekcja VIII: Termin składania ofert','otwarcie_ofert':'sekcja VIII: Termin otwarcia ofert',
 'strona_postepowania':'sekcja III: Adres strony internetowej prowadzonego postępowania','skladanie_ofert':'sekcja VIII: Miejsce składania ofert / sekcja III: środki komunikacji elektronicznej',
 'numer_referencyjny':'sekcja IV: Numer referencyjny','okres_umowy':'sekcja IV: Okres realizacji zamówienia albo umowy ramowej','kryteria':'sekcja IV: Kryteria oceny ofert (nazwa, waga)',
 'czesci':'sekcja IV: Część n – Krótki opis przedmiotu zamówienia'}
ZR_TED={'nip_regon':'eForms BT-501 (organisation-identifier-buyer)','adres':'eForms BT-510/BT-512/BT-513 (adres organizacji zamawiającego)','email':'eForms BT-506 (organisation-email-buyer)',
 'www':'eForms BT-505 (organisation-internet-address-buyer)','termin_ofert':'eForms BT-131 (deadline-receipt-tender-date/time-lot)','otwarcie_ofert':'eForms BT-132 (public-opening-date/time-lot)',
 'strona_postepowania':'eForms BT-15 (document-url-lot)','skladanie_ofert':'eForms BT-18 (submission-url-lot)','numer_referencyjny':'eForms BT-22 (internal-identifier-proc)',
 'okres_umowy':'eForms BT-36/BT-537/BT-538 (okres obowiązywania, części)','kryteria':'eForms BT-539/BT-734/BT-541 (kryteria udzielenia zamówienia)','czesci':'eForms BT-137/BT-21/BT-24 (identyfikator, tytuł, opis części)'}
TED_POLA_SZCZ=['publication-number','notice-type','publication-date','organisation-identifier-buyer','organisation-name-buyer','organisation-email-buyer','organisation-internet-address-buyer',
 'organisation-street-buyer','organisation-post-code-buyer','organisation-city-buyer','deadline-receipt-tender-date-lot','deadline-receipt-tender-time-lot','public-opening-date-lot',
 'public-opening-time-lot','document-url-lot','submission-url-lot','internal-identifier-proc','duration-period-value-lot','duration-period-unit-lot','contract-duration-start-date-lot',
 'contract-duration-end-date-lot','award-criterion-type-lot','award-criterion-name-lot','award-criterion-number-lot','identifier-lot','title-lot','description-lot','description-proc','additional-information-lot']
# ---------- dane osobowe ----------
INSTYTUCJONALNE=re.compile(r'zam[oó]w|przet[a]rg|^zp|^dzp|[._-]zp|zp[._-]|^dz[a-z]{0,3}$|^sz?zp|^wzp|^zzp|^dzz|^dl$|sekretariat|sekr|kancelari|info|biuro|office|szpit[a]l|zaopatrz|apteka|administr|kontakt|dyrekc|logisty|inwestyc|poczta|centrala|oferty|zakup|tender|procure|purchas|^bzp|ezam|^zam|dzial|^sp|^spzoz|^zoz|^wss|^uck|^usk|^szp|^dyr|^dop|^dzl|^zpu|^zpi|^umowy|^post|^rejestr|^mail|^skrzynka|^ogolny|^general|^contact|^admin|^dfz|^oz|^wz|^dza|^dao|^dl|^cz',re.I)
def email_instytucjonalny(e):
    e=(e or '').strip().strip('.,;')
    m=re.fullmatch(r'([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)',e)
    if not m: return None
    lok=m.group(1).lower(); seg=[s for s in re.split(r'[._+-]',lok) if s]
    if any(s in IMIONA for s in seg): return None
    if not INSTYTUCJONALNE.search(lok): return None
    return e
TEL=re.compile(r'(?i)(?:\b(?:tel|telefon|fax|faks|kom|tel\.?\s*kom)\b\.?\s*[:.]?\s*)?(?<![\d/])(?:\+?48[\s-]?)?(?:\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}|\d{3}[\s-]\d{3}[\s-]\d{3})(?![\d/])')
TYTUL=re.compile(r'\b(?:Pan(?:i|a|em|u)?|mgr|dr|l[e]k\.|inż\.|prof\.|osob[aąy] (?:do kontaktu|upoważnion\w*|kontaktow\w*))\s*:?\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:[\s-]+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?')
WYRAZ=re.compile(r'[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+')
PRZED_ADRES=re.compile(r'(?:ul\.|al\.|aleja|ulica|im\.|imienia|pl\.|plac|os\.|osiedle|rondo|św\.|bł\.|ks\.|gen\.|Szpit[a]l\w*|Instytut\w*|Centrum)\s*$',re.I)
def imie_nazwisko(t):
    """Pary 'Imię Nazwisko' poza nazwami ulic i patronów (do pominięcia)."""
    out=[]
    for m in re.finditer(r'\b([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)\b',t):
        if m.group(1).lower() in IMIONA and not PRZED_ADRES.search(t[max(0,m.start()-25):m.start()]): out.append(m.span())
    return out
def czysc(t):
    """Usuwa z tekstu ogłoszenia możliwe dane kontaktowe osób: imienne e-maile, telefony, imiona i nazwiska."""
    if not t: return t
    t=re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+',lambda m:m.group(0) if email_instytucjonalny(m.group(0)) else '[pominięto]',t)
    t=TEL.sub(lambda m:'[pominięto]' if re.search(r'\d{2}',m.group(0)) and len(re.sub(r'\D','',m.group(0)))>=9 else m.group(0),t)
    t=TYTUL.sub('[pominięto]',t)
    for a,b in reversed(imie_nazwisko(t)): t=t[:a]+'[pominięto]'+t[b:]
    return t
def url_ok(u):
    u=(u or '').strip().rstrip('.,;)')
    if re.match(r'www\.[\w-]+\.[\w.-]+',u,re.I): u='https://'+u   # adres podany w ogłoszeniu bez protokołu
    return u if re.match(r'https?://[\w.-]+\.[a-z]{2,}',u,re.I) and '@' not in u.split('/')[2] else None
def cut(s,n): s=(s or '').strip(); return s if len(s)<=n else s[:n].rstrip()+'…'
def pole(w,z): return {'w':w if w not in (None,'',[]) else BRAK,'z':z}
# ---------- BZP ----------
def bzp_linie(h):
    t=re.sub(r'<style.*?</style>','',h or '',flags=re.S|re.I)
    t=re.sub(r'<(br|/p|/div|/h\d|/li|/tr|/td)[^>]*>','\n',t,flags=re.I); t=html.unescape(re.sub(r'<[^>]+>',' ',t))
    t=re.sub(r'[ \t\xa0]+',' ',t); return [l.strip() for l in t.split('\n') if l.strip()]
NUMER=re.compile(r'^\d+(?:\.\d+)*\.?\)')
def _val(L,etykieta,od=0,do=None):
    for i in range(od,do if do is not None else len(L)):
        l=L[i]; j=l.find(etykieta)
        if j>=0:
            v=l[j+len(etykieta):].strip(' :')
            if not v and i+1<len(L) and not NUMER.match(L[i+1]): v=L[i+1]
            return v.strip()
    return None
def z_bzp(x):
    """x: ogłoszenie z API tablicy BZP (z htmlBody). Zwraca dict pól (bez sekcji-źródeł; te dodaje opakuj())."""
    L=bzp_linie(x.get('htmlBody')); T='\n'.join(L)
    s2=next((i for i,l in enumerate(L) if l.startswith('SEKCJA II')),len(L))
    v={}
    nip=_val(L,'Krajowy Numer Identyfikacyjny',0,s2); v['nip_regon']=re.sub(r'\s+',' ',nip) if nip and re.search(r'\d{9}',nip.replace(' ','').replace('-','')) else (nip or x.get('organizationNationalId'))
    ul=_val(L,'Ulica:',0,s2); kod=_val(L,'Kod pocztowy:',0,s2); mi=_val(L,'Miejscowość:',0,s2)
    v['adres']=re.sub(r'\s+',' ',', '.join(p for p in [ul,' '.join(q for q in [kod,mi] if q)] if p)).strip() or None
    e=_val(L,'Adres poczty elektronicznej:',0,s2)
    v['email']=(email_instytucjonalny(e) or 'pominięto (adres mógł być imienny) – zob. ogłoszenie') if e else None
    v['www']=url_ok(_val(L,'Adres strony internetowej zamawiającego:',0,s2))
    def dt(lbl):
        s=_val(L,lbl); m=re.search(r'(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?',s or '')
        return (m.group(1)+(' '+m.group(2) if m.group(2) else ' (godzina: brak w ogłoszeniu)')) if m else None
    v['termin_ofert']=dt('Termin składania ofert:'); v['otwarcie_ofert']=dt('Termin otwarcia ofert:')
    i=next((i for i,l in enumerate(L) if 'Adres strony internetowej prowadzonego postępowania' in l),None)
    sp=None
    if i is not None:
        m=re.search(r'(?:https?://|www\.)[^\s<>"\']+',' '.join(L[i:i+2])); sp=url_ok(m.group(0)) if m else None
    v['strona_postepowania']=sp
    ms=_val(L,'Miejsce składania ofert:'); m=re.search(r'(?:https?://|www\.)[^\s<>"\']+',ms or '')
    sk=url_ok(m.group(0)) if m else None
    if not sk:
        k=_val(L,'komunikował się z wykonawcami - adres strony internetowej:'); m=re.search(r'(?:https?://|www\.)[^\s<>"\']+',k or ''); sk=url_ok(m.group(0)) if m else None
    v['skladanie_ofert']=sk
    nr=_val(L,'Numer referencyjny:'); v['numer_referencyjny']=czysc(cut(nr,120)) if nr else None
    # części
    idx=[(i,int(m.group(1))) for i,l in enumerate(L) for m in [re.fullmatch(r'Część\s+(\d+)',l)] if m]
    s4=next((i for i,l in enumerate(L) if l.startswith('SEKCJA IV')),0); s5=next((i for i,l in enumerate(L) if l.startswith('SEKCJA V')),len(L))
    bloki=[(nr_,a,(idx[k+1][0] if k+1<len(idx) else s5)) for k,(a,nr_) in enumerate(idx)] or [(None,s4,s5)]
    cz=[]; okr=[]; kr=[]
    for nr_,a,b in bloki:
        B=L[a:b]
        j=next((k for k,l in enumerate(B) if 'Krótki opis przedmiotu zamówienia' in l),None)
        if j is not None and nr_ is not None:
            o=[]; 
            for l in B[j+1:]:
                if NUMER.match(l): break
                o.append(l)
            cz.append({'nr':f'Część {nr_}','opis':czysc(cut(' '.join(o),700))})
        o=_val(B,'Okres realizacji zamówienia albo umowy ramowej:')
        if not o:
            o1=_val(B,'Data rozpoczęcia:') or _val(B,'Data rozpoczęcia realizacji'); o2=_val(B,'Data zakończenia:') or _val(B,'Data zakończenia realizacji')
            o=' – '.join(p for p in [o1,o2] if p) or None
        if o: okr.append((nr_,czysc(cut(o,120))))
        nz=[k for k,l in enumerate(B) if 'Nazwa kryterium:' in l]; kk=[]
        for k in nz:
            n=B[k].split('Nazwa kryterium:',1)[1].strip(); w=_val(B[k+1:k+4],'Waga:')
            kk.append(f"{czysc(cut(n,80))} – {w}" if w else czysc(cut(n,80)))
        if kk: kr.append((nr_,'; '.join(kk)))
    def zlacz(pary):
        if not pary: return None
        u=list(dict.fromkeys(p[1] for p in pary))
        return u[0] if len(u)==1 else ' | '.join(f"Część {n}: {t}" if n is not None else t for n,t in pary)
    v['okres_umowy']=zlacz(okr); v['kryteria']=zlacz(kr); v['czesci']=cz or None
    return v
# ---------- TED ----------
def _l(x):
    if x is None: return []
    if isinstance(x,dict): x=x.get('pol') or x.get('mul') or x.get('eng') or next(iter(x.values()),[])
    return x if isinstance(x,list) else [x]
def ted_czas(d,t):
    """'2026-11-30+01:00' + '08:55:00+01:00' -> '2026-11-30 08:55' (czas polski)."""
    if not d: return None
    m=re.match(r'(\d{4}-\d{2}-\d{2})(Z|[+-]\d{2}:\d{2})?',d)
    if not m: return None
    if not t: return m.group(1)+' (godzina: brak w ogłoszeniu)'
    mt=re.match(r'(\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:\d{2})?',t)
    if not mt: return m.group(1)+' (godzina: brak w ogłoszeniu)'
    tz=mt.group(4) or m.group(2) or '+00:00'; tz='+00:00' if tz=='Z' else tz
    x=datetime.datetime.fromisoformat(f"{m.group(1)}T{mt.group(1)}:{mt.group(2)}:00{tz}").astimezone(PL)
    return x.strftime('%Y-%m-%d %H:%M')
JEDN={'MONTH':'mies.','DAY':'dni','YEAR':'lat(a)','WEEK':'tyg.'}
KRYT={'price':'Cena','quality':'Jakość','cost':'Koszt'}
def ident(s):
    d=re.sub(r'\D','',s or '')
    if len(d)==10: return f'NIP {d}'
    if len(d) in (9,14): return f'REGON {d}'
    return s or None
def z_ted(n):
    v={}; ids=[i for i in dict.fromkeys(_l(n.get('organisation-identifier-buyer'))) if i]
    v['nip_regon']='; '.join(ident(i) for i in ids) or None
    ul=_l(n.get('organisation-street-buyer')); kod=_l(n.get('organisation-post-code-buyer')); mi=_l(n.get('organisation-city-buyer'))
    v['adres']=re.sub(r'\s+',' ',', '.join(p for p in [ul[0] if ul else None,' '.join(q for q in [kod[0] if kod else None,mi[0] if mi else None] if q)] if p)).strip() or None
    es=[e for e in dict.fromkeys(_l(n.get('organisation-email-buyer'))) if e]
    ok=[email_instytucjonalny(e) for e in es]
    v['email']=(ok[0] if ok and ok[0] else 'pominięto (adres mógł być imienny) – zob. ogłoszenie') if es else None
    w=[url_ok(u) for u in _l(n.get('organisation-internet-address-buyer'))]; v['www']=next((u for u in w if u),None)
    def para(dk,tk):
        ds=_l(n.get(dk)); ts=_l(n.get(tk)); xs=[ted_czas(d,ts[i] if i<len(ts) else (ts[0] if ts else None)) for i,d in enumerate(ds)]
        u=list(dict.fromkeys(x for x in xs if x))
        return None if not u else (u[0] if len(u)==1 else '; '.join(u)+' (różne dla części)')
    v['termin_ofert']=para('deadline-receipt-tender-date-lot','deadline-receipt-tender-time-lot'); v['otwarcie_ofert']=para('public-opening-date-lot','public-opening-time-lot')
    d=[u for u in dict.fromkeys(url_ok(u) for u in _l(n.get('document-url-lot'))) if u]; s=[u for u in dict.fromkeys(url_ok(u) for u in _l(n.get('submission-url-lot'))) if u]
    v['strona_postepowania']=d[0] if d else None; v['skladanie_ofert']=s[0] if s else None
    ip=n.get('internal-identifier-proc'); ip=_l(ip)[0] if _l(ip) else None; v['numer_referencyjny']=czysc(cut(ip,120)) if ip else None
    lots=_l(n.get('identifier-lot')); dv=_l(n.get('duration-period-value-lot')); du=_l(n.get('duration-period-unit-lot'))
    sd=_l(n.get('contract-duration-start-date-lot')); ed=_l(n.get('contract-duration-end-date-lot'))
    okr=[f"{a} {JEDN.get(b,b.lower())}" for a,b in zip(dv,du)] or [f"{(a or '')[:10]} – {(b or '')[:10]}" for a,b in zip(sd,ed)]
    u=list(dict.fromkeys(okr)); v['okres_umowy']=None if not u else (u[0] if len(u)==1 else '; '.join(u)+' (różne dla części)')
    ty=_l(n.get('award-criterion-type-lot')); nm=_l(n.get('award-criterion-name-lot')); nu=_l(n.get('award-criterion-number-lot'))
    kk=[]
    for i,t in enumerate(ty):
        nazwa=nm[i] if len(nm)==len(ty) else KRYT.get(t,t)
        kk.append(f"{czysc(cut(nazwa,80))} – {nu[i]}" if len(nu)==len(ty) else czysc(cut(nazwa,80)))
    u=list(dict.fromkeys(kk)); v['kryteria']='; '.join(u)+(' (wagi w ogłoszeniu – różne części)' if len(lots)>1 and len(kk)%max(len(lots),1) else '') if u else None
    ti=_l(n.get('title-lot')); de=_l(n.get('description-lot'))
    v['czesci']=[{'nr':lots[i] if i<len(lots) else f'część {i+1}','tytul':czysc(cut(t,200)),'opis':czysc(cut(de[i] if i<len(de) else '',700))} for i,t in enumerate(ti)] if len(ti)>1 or len(lots)>1 else None
    return v
# ---------- zapis w rekordzie ----------
def opakuj(v,zrodlo,ogl,pobrano):
    ZR=ZR_BZP if zrodlo=='BZP' else ZR_TED
    return {'ogloszenie':ogl,'pobrano':pobrano,'pola':{k:pole(v.get(k),ZR[k]) for k in POLA}}
def wybierz_ogloszenie(r):
    """Ogłoszenie źródłowe pól: najnowsze ogłoszenie o zamówieniu; gdy go brak – najnowsze ogłoszenie postępowania."""
    h=sorted(r['historia'],key=lambda h:(h.get('data') or '',h.get('numer') or ''))
    cn=[x for x in h if x.get('typ')=='ContractNotice' or str(x.get('typ') or '').startswith('cn')]
    return (cn or h)[-1] if h else None
