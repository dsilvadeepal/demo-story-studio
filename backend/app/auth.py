import hashlib,hmac,os,secrets,time
from collections import defaultdict
from urllib.parse import urlparse
from fastapi import Request,HTTPException
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired
_attempts=defaultdict(list)
def hash_password(password):
    salt=secrets.token_hex(16)
    digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return salt+':'+digest

def verify_password(password):
    configured=os.environ.get('OWNER_PASSWORD_HASH','')
    if not configured: raise HTTPException(503,'Owner access is not configured')
    salt,expected=configured.split(':',1)
    digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return hmac.compare_digest(digest,expected)

def signer():
    secret=os.getenv('SESSION_SECRET','')
    if len(secret)<32: raise HTTPException(503,'Session secret is not configured')
    return URLSafeTimedSerializer(secret,salt='studio-owner-session')

def check_origin(request):
    origin=request.headers.get('origin')
    if origin and urlparse(origin).netloc!=request.headers.get('host'): raise HTTPException(403,'Cross-origin requests are not allowed')

def require_owner(request:Request):
    token=request.cookies.get('studio_session')
    if not token: raise HTTPException(401,'Sign in to your private Studio')
    try:
        payload=signer().loads(token,max_age=8*3600)
        if payload.get('owner') is not True: raise BadSignature('owner')
    except (BadSignature,SignatureExpired): raise HTTPException(401,'Session expired; sign in again')

def rate_limit(request):
    key=request.client.host if request.client else 'unknown'; now=time.monotonic()
    _attempts[key]=[x for x in _attempts[key] if now-x<60]
    if len(_attempts[key])>=10: raise HTTPException(429,'Too many attempts; wait one minute')
    _attempts[key].append(now)
