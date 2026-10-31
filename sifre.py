# -*- coding: utf-8 -*-
"""Diskteki gizli bilgilerin (mağaza erişim anahtarları, client secret, oturum anahtarı) şifrelenmesi.

Yalnızca standart kütüphane: anahtar akışı HMAC-SHA256 sayaç kipiyle üretilir, şifreli metin HMAC-SHA256 ile
imzalanır (önce şifrele, sonra imzala). Değiştirilmiş ya da başka anahtarla şifrelenmiş değer açılmaz.

Ana anahtar sırasıyla:
  1. SEOVISI_ANAHTAR ortam değişkeni (sunucu kipinde önerilen; anahtar veriyle aynı diskte durmaz),
  2. data/anahtar.key dosyası (yoksa ilk kullanımda üretilir).
Ana anahtar kaybolursa şifreli değerler açılamaz; mağazalar Ideasoft'a yeniden bağlanır.
"""
import base64
import hashlib
import hmac
import os
import secrets
import threading

PREFIX = "sifreli:v1:"
KEY_PATH = ""                     # app.py ayarlar: data/anahtar.key
ENV = "SEOVISI_ANAHTAR"
_NONCE, _TAG = 16, 32
_key, _lock = None, threading.Lock()


class SifreHatasi(Exception):
    pass


def _read_or_create(path):
    try:
        with open(path, "rb") as f:
            raw = f.read().strip()
    except FileNotFoundError:
        raw = secrets.token_hex(32).encode()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:          # başka bir işlem aynı anda üretti; onunkini kullan
            return _read_or_create(path)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
    if not raw:
        raise SifreHatasi(f"{path} boş.")
    return raw


def master():
    global _key
    with _lock:
        if _key is None:
            env = os.environ.get(ENV, "").strip()
            if env:
                raw = env.encode()
            elif KEY_PATH:
                raw = _read_or_create(KEY_PATH)
            else:
                raise SifreHatasi("Şifreleme anahtarının yeri ayarlanmadı.")
            _key = hashlib.sha256(b"seovisi-ana-anahtar\0" + raw).digest()
        return _key


def reset():
    """Anahtarı yeniden okutur (testler ve anahtar değişimi için)."""
    global _key
    with _lock:
        _key = None


def _keys():
    m = master()
    return hmac.new(m, b"sifreleme", hashlib.sha256).digest(), hmac.new(m, b"imza", hashlib.sha256).digest()


def _stream(k, nonce, n):
    out, i = bytearray(), 0
    while len(out) < n:
        out += hmac.new(k, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        i += 1
    return bytes(out[:n])


def is_encrypted(v):
    return isinstance(v, str) and v.startswith(PREFIX)


def encrypt(text):
    ek, mk = _keys()
    pt = text.encode("utf-8")
    nonce = secrets.token_bytes(_NONCE)
    ct = bytes(a ^ b for a, b in zip(pt, _stream(ek, nonce, len(pt))))
    tag = hmac.new(mk, PREFIX.encode() + nonce + ct, hashlib.sha256).digest()
    return PREFIX + base64.urlsafe_b64encode(nonce + ct + tag).decode("ascii")


def decrypt(value):
    if not is_encrypted(value):
        raise SifreHatasi("Şifreli değer değil.")
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):].encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise SifreHatasi("Şifreli değer bozuk.")
    if len(raw) < _NONCE + _TAG:
        raise SifreHatasi("Şifreli değer bozuk.")
    nonce, ct, tag = raw[:_NONCE], raw[_NONCE:-_TAG], raw[-_TAG:]
    ek, mk = _keys()
    if not hmac.compare_digest(hmac.new(mk, PREFIX.encode() + nonce + ct, hashlib.sha256).digest(), tag):
        raise SifreHatasi("Şifreli değer açılamadı (anahtar farklı ya da değer değiştirilmiş).")
    return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct)))).decode("utf-8")
