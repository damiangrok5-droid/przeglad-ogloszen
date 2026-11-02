// Buduje zaszyfrowaną wersję strony (Node ≥20, tylko WebCrypto).
// Użycie: SITE_PASSWORD=... node szyfruj.mjs <katalog_strony> <katalog_wyjściowy>
// Hasło wyłącznie ze zmiennej środowiskowej; skrypt go nie zapisuje ani nie wypisuje.
// Jawne pliki wyjścia: index.html (neutralna bramka), manifest.webmanifest, robots.txt, .nojekyll, dane/klucz.json (sól, iteracje, test).
// Zaszyfrowane (AES-256-GCM, klucz PBKDF2-SHA256, 600 000 iteracji, sól losowa na build): dane/aplikacja.enc (właściwa aplikacja) i każdy dane/*.json -> dane/*.enc.
import {readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync, existsSync, copyFileSync} from 'node:fs';
import {join} from 'node:path';
const {subtle} = globalThis.crypto;
const [src, out] = process.argv.slice(2);
const pw = process.env.SITE_PASSWORD;
if (!src || !out) { console.error('użycie: node szyfruj.mjs <strona> <wyjście>'); process.exit(2); }
if (!pw || pw.length < 12) { console.error('SITE_PASSWORD brak lub krótsze niż 12 znaków'); process.exit(2); }
const ITER = 600000;
const b64 = u => Buffer.from(u).toString('base64');
const rnd = n => globalThis.crypto.getRandomValues(new Uint8Array(n));
const salt = rnd(16);
const base = await subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
const key = await subtle.deriveKey({name:'PBKDF2', hash:'SHA-256', salt, iterations:ITER}, base, {name:'AES-GCM', length:256}, false, ['encrypt']);
async function enc(text){ const iv = rnd(12); const ct = await subtle.encrypt({name:'AES-GCM', iv}, key, new TextEncoder().encode(text)); return {iv:b64(iv), ct:b64(ct)}; }
if (existsSync(out)) rmSync(out, {recursive:true});
mkdirSync(join(out,'dane'), {recursive:true});
for (const f of ['bramka.html','aplikacja.html']) {
  if (!/<meta name="robots" content="noindex/.test(readFileSync(join(src,f),'utf8'))) { console.error('brak meta noindex w '+f); process.exit(3); }
}
copyFileSync(join(src,'bramka.html'), join(out,'index.html'));
copyFileSync(join(src,'manifest.webmanifest'), join(out,'manifest.webmanifest'));
let app = readFileSync(join(src,'aplikacja.html'),'utf8').replace(/<html([^>]*)>/, (m,a)=>a.includes('data-szyfr')?m:`<html${a} data-szyfr="1">`);
writeFileSync(join(out,'dane','aplikacja.enc'), JSON.stringify(await enc(app)));
writeFileSync(join(out,'robots.txt'), 'User-agent: *\nDisallow: /\n');
writeFileSync(join(out,'.nojekyll'), '');
const pliki = readdirSync(join(src,'dane')).filter(f=>f.endsWith('.json'));
for (const f of pliki) writeFileSync(join(out,'dane',f.replace(/\.json$/,'.enc')), JSON.stringify(await enc(readFileSync(join(src,'dane',f),'utf8'))));
writeFileSync(join(out,'dane','klucz.json'), JSON.stringify({v:2, kdf:'PBKDF2-SHA256', iter:ITER, salt:b64(salt), alg:'AES-256-GCM', test: await enc('ok')}));
console.log(`OK: aplikacja + ${pliki.length} plików danych zaszyfrowanych, iteracje ${ITER}`);
