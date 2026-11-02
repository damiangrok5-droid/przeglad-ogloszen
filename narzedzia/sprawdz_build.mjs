// Weryfikacja zaszyfrowanego buildu: odszyfrowuje dane/aplikacja.enc i wszystkie dane/*.enc hasłem z SITE_PASSWORD,
// sprawdza, że aplikacja zawiera właściwą treść, a pliki danych są poprawnym JSON-em identycznym ze źródłem (jeśli podano katalog źródłowy).
// Użycie: SITE_PASSWORD=... node sprawdz_build.mjs <build> [<strona/dane>]
import {readFileSync, readdirSync, existsSync} from 'node:fs'; import {join} from 'node:path';
const {subtle} = globalThis.crypto; const [b, src] = process.argv.slice(2); const pw = process.env.SITE_PASSWORD;
if (!pw) { console.error('brak SITE_PASSWORD'); process.exit(2); }
const k = JSON.parse(readFileSync(join(b,'dane','klucz.json'),'utf8')); const u = s => Buffer.from(s,'base64');
const key = await subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt:u(k.salt),iterations:k.iter},
  await subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']),{name:'AES-GCM',length:256},false,['decrypt']);
const dec = async o => new TextDecoder().decode(await subtle.decrypt({name:'AES-GCM',iv:u(o.iv)},key,u(o.ct)));
const wyn = {iter:k.iter, bledy:[]};
if (k.iter < 600000) wyn.bledy.push('iteracje < 600000');
if (await dec(k.test) !== 'ok') wyn.bledy.push('test klucza');
const app = await dec(JSON.parse(readFileSync(join(b,'dane','aplikacja.enc'),'utf8')));
wyn.aplikacja_bajtow = app.length; if (!/<title>[^<]+<\/title>/.test(app) || !/data-szyfr="1"/.test(app)) wyn.bledy.push('treść aplikacji');
wyn.pliki = 0;
for (const f of readdirSync(join(b,'dane')).filter(f=>f.endsWith('.enc') && f!=='aplikacja.enc')) {
  const raw = readFileSync(join(b,'dane',f));
  if (raw.subarray(0,3).toString() === 'PO1') { // stan aktualizacji (stan.mjs): własna sól, oczekiwany gzip
    const kk = await subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt:raw.subarray(3,19),iterations:600000},
      await subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']),{name:'AES-GCM',length:256},false,['decrypt']);
    try { const pt = new Uint8Array(await subtle.decrypt({name:'AES-GCM',iv:raw.subarray(19,31)},kk,raw.subarray(31)));
          if (pt[0]!==0x1f || pt[1]!==0x8b) wyn.bledy.push('stan nie jest gzip: '+f); wyn.stan = (wyn.stan||0)+1; }
    catch (e) { wyn.bledy.push('nie odszyfrowano: '+f); }
    continue;
  }
  const t = await dec(JSON.parse(raw.toString('utf8'))); JSON.parse(t); wyn.pliki++;
  const s = src && join(src, f.replace(/\.enc$/,'.json')); if (s && existsSync(s) && readFileSync(s,'utf8') !== t) wyn.bledy.push('różnica: '+f);
}
console.log(JSON.stringify(wyn)); process.exit(wyn.bledy.length ? 1 : 0);
