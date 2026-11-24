"""Server-side username/password verification for a single-process prototype."""
import base64,hashlib,hmac,json,secrets,threading,time
ITERATIONS=600_000

def password_hash(password):
    if not isinstance(password,str) or len(password)<12:raise ValueError('Use a password of at least 12 characters.')
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,ITERATIONS)
    return dict(salt=base64.b64encode(salt).decode(),digest=base64.b64encode(digest).decode(),iterations=ITERATIONS)

def verify_password(password,stored):
    try:
        if not isinstance(password,str) or len(password)>1024:return False
        rounds=int(stored['iterations'])
        if not 100_000<=rounds<=2_000_000:return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(stored['salt'],validate=True),rounds)
        return hmac.compare_digest(actual,base64.b64decode(stored['digest'],validate=True))
    except (ValueError,KeyError,TypeError):return False

def validate_config(config):
    if not isinstance(config,dict) or config.get('version')!=1 or not isinstance(config.get('accounts'),dict):raise ValueError('Invalid login configuration.')
    roles=[]
    for username,account in config['accounts'].items():
        if not isinstance(username,str) or not username or len(username)>128 or username!=username.strip().casefold() or not isinstance(account,dict) or account.get('role') not in ('owner','demo'):raise ValueError('Invalid login account.')
        stored=account.get('password')
        if not isinstance(stored,dict) or not all(k in stored for k in ('salt','digest','iterations')):raise ValueError('Missing password hash.')
        try:
            if not isinstance(stored['salt'],str) or not isinstance(stored['digest'],str):raise ValueError('Invalid password hash')
            if len(base64.b64decode(stored['salt'],validate=True))!=16 or len(base64.b64decode(stored['digest'],validate=True))!=32:raise ValueError('Invalid password hash')
            if type(stored['iterations']) is not int or not 100_000<=stored['iterations']<=2_000_000:raise ValueError('Invalid password hash')
        except (ValueError,TypeError):raise ValueError('Invalid password hash.')
        roles.append(account['role'])
    if roles.count('owner')!=1:raise ValueError('Exactly one owner is required.')
    return config

class LoginVerifier:
    """Shared account-based throttling. Not a distributed identity provider."""
    def __init__(self):
        self.failures={};self.lock=threading.Lock();self.dummy=password_hash(secrets.token_urlsafe(24))
    def authenticate(self,config,username,password,now=None):
        now=time.monotonic() if now is None else now
        username=str(username).strip().casefold()[:128]
        # Unknown names share one bucket; attacker-supplied usernames cannot grow memory.
        account=config['accounts'].get(username);bucket=username if account else '__unknown__'
        with self.lock:
            attempts=[t for t in self.failures.get(bucket,[]) if now-t<60]
            if len(attempts)>=5:return None,'Too many attempts. Wait one minute and try again.'
            good=verify_password(password,account['password'] if account else self.dummy)
            if not good or account is None:
                self.failures[bucket]=attempts+[now]
                return None,'Username or password is incorrect.'
            self.failures.pop(bucket,None)
            return dict(username=username,role=account['role']),None
