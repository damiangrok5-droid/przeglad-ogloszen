# Test przeglądarkowy zaszyfrowanego buildu (blokuje publikację): neutralna bramka, złe hasło odrzucone,
# po haśle aplikacja wczytuje dane (licznik + wiersze tabeli), brak błędów JS, "Zablokuj" wraca do bramki.
# Hasło tylko z env SITE_PASSWORD. Rozmycie tła NIE jest wyłączane (Chromium obsługuje backdrop-filter).
# Użycie: python3 testy/test_przegladarka.py <_site> [--port 18790] [--wynik plik.json]
import os,sys,json,re,subprocess,time,argparse
from playwright.sync_api import sync_playwright
ap=argparse.ArgumentParser(); ap.add_argument('site'); ap.add_argument('--port',type=int,default=18790); ap.add_argument('--wynik'); A=ap.parse_args()
PW=os.environ.get('SITE_PASSWORD') or sys.exit('brak SITE_PASSWORD')
pz=os.path.join(os.path.dirname(os.path.abspath(__file__)),'zakazane.json')
ZK=json.load(open(pz,encoding='utf-8')) if os.path.exists(pz) else sys.exit('brak testy/zakazane.json – najpierw: python3 narzedzia/pakiet.py otworz')
ZAK=re.compile('|'.join(ZK['wzorce']),re.I); TA=ZK['tytul_aplikacji']  # wzorce i oczekiwany tytuł aplikacji z zaszyfrowanego pakietu
srv=subprocess.Popen([sys.executable,'-m','http.server',str(A.port),'--bind','127.0.0.1','-d',A.site],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
r={}; U=f'http://127.0.0.1:{A.port}/'
try:
  with sync_playwright() as p:
    br=p.chromium.launch(); pg=br.new_page(viewport={'width':390,'height':844}); bl=[]
    pg.on('pageerror',lambda e: bl.append(str(e))); pg.on('console',lambda m: bl.append(m.text) if m.type=='error' else None)
    pg.goto(U); pg.wait_for_selector('#haslo')
    r['tytul_bramki']=pg.title(); r['zakazane_na_bramce']=sorted(set(m.group(0) for m in ZAK.finditer(pg.content())))
    pg.fill('#haslo','niepoprawne-haslo-testowe-0000'); pg.click('#ok'); pg.wait_for_timeout(5000)
    r['zle_haslo_odrzucone']=pg.is_visible('#haslo')
    pg.fill('#haslo',PW); pg.click('#ok')
    pg.wait_for_function("()=>document.querySelectorAll('#tbody tr').length>0",timeout=90000)
    r['wierszy']=pg.locator('#tbody tr').count(); r['licznik']=pg.inner_text('#licznik')[:120]
    r['tresc_po_odblokowaniu']=TA in pg.inner_text('body') or pg.title()==TA
    pg.reload(); pg.wait_for_function("()=>document.querySelectorAll('#tbody tr').length>0",timeout=90000); r['sesja_po_przeladowaniu']=True
    z=pg.locator('#zablokuj'); z.scroll_into_view_if_needed(); z.click(); pg.wait_for_selector('#haslo',timeout=20000)
    pg.reload(); pg.wait_for_selector('#haslo'); r['po_zablokowaniu_bramka']=TA not in pg.inner_text('body') and not ZAK.search(pg.content())
    r['bledy_js']=[b for b in bl if 'Failed to load resource' not in b][:5]; br.close()
except Exception as e: r['wyjatek']=str(e)[:400]
finally: srv.terminate()
ok=(not r.get('wyjatek') and r.get('tytul_bramki')==ZK['tytul_bramki'] and not r.get('zakazane_na_bramce') and r.get('zle_haslo_odrzucone')
    and r.get('wierszy',0)>0 and r.get('tresc_po_odblokowaniu') and r.get('po_zablokowaniu_bramka') and not r.get('bledy_js'))
print(('PASS' if ok else 'FAIL')+'  przegladarka  '+json.dumps(r,ensure_ascii=False))
if A.wynik: json.dump({'wynik':'PASS' if ok else 'FAIL',**r},open(A.wynik,'w'),ensure_ascii=False,indent=1)
sys.exit(0 if ok else 1)
