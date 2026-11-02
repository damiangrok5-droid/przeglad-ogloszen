// Szyfrowanie stanu aktualizacji (stan.json.gz) tym samym hasłem co strona; plik samowystarczalny: "PO1" | sól(16) | iv(12) | szyfrogram.
// Użycie: SITE_PASSWORD=... node stan.mjs szyfruj <wejście.gz> <wyjście.enc> | odszyfruj <wejście.enc> <wyjście.gz>
import {readFileSync, writeFileSync} from 'node:fs';
const {subtle} = globalThis.crypto; const ITER = 600000;
const [tryb, we, wy] = process.argv.slice(2); const pw = process.env.SITE_PASSWORD;
if (!pw || pw.length < 12) { console.error('SITE_PASSWORD brak lub krótsze niż 12 znaków'); process.exit(2); }
const klucz = async (salt, u) => subtle.deriveKey({name:'PBKDF2', hash:'SHA-256', salt, iterations:ITER},
  await subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']), {name:'AES-GCM', length:256}, false, [u]);
const MAG = Buffer.from('PO1');
if (tryb === 'szyfruj') {
  const salt = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await subtle.encrypt({name:'AES-GCM', iv}, await klucz(salt,'encrypt'), readFileSync(we)));
  writeFileSync(wy, Buffer.concat([MAG, salt, iv, ct])); console.log('OK stan zaszyfrowany', ct.length, 'B');
} else if (tryb === 'odszyfruj') {
  const b = readFileSync(we); if (!b.subarray(0,3).equals(MAG)) { console.error('zły format pliku stanu'); process.exit(3); }
  try { const pt = await subtle.decrypt({name:'AES-GCM', iv:b.subarray(19,31)}, await klucz(b.subarray(3,19),'decrypt'), b.subarray(31));
        writeFileSync(wy, Buffer.from(pt)); console.log('OK stan odszyfrowany', pt.byteLength, 'B'); }
  catch (e) { console.error('nie udało się odszyfrować stanu (złe hasło lub uszkodzony plik)'); process.exit(4); }
} else { console.error('tryb: szyfruj | odszyfruj'); process.exit(2); }
