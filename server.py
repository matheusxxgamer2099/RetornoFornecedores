"""Portal de fornecedores. Python 3.12+, somente biblioteca padrão."""
import os, json, sqlite3, secrets, hashlib, hmac, time, re
from datetime import date
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
DB = os.environ.get('DATABASE_PATH', str(ROOT / 'data' / 'portal.db'))
ADMIN_KEY = os.environ.get('ADMIN_API_KEY', '')
BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:8000').rstrip('/')

def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS requests (
          id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
          supplier TEXT NOT NULL, email TEXT NOT NULL, expires INTEGER NOT NULL,
          items TEXT NOT NULL, answers TEXT, status TEXT NOT NULL DEFAULT 'pending',
          responder TEXT, updated INTEGER, created INTEGER NOT NULL);
        ''')

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def clean(value, limit=200):
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValueError('Texto inválido ou muito longo.')
    return value.strip()

def create_request(data):
    supplier = clean(data.get('supplier'))
    email = clean(data.get('email', ''))
    if not supplier: raise ValueError('Informe o fornecedor.')
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 1000:
        raise ValueError('Informe de 1 a 1000 itens por cobrança.')
    prepared, ids = [], set()
    for item in items:
        if not isinstance(item, dict): raise ValueError('Item inválido.')
        row = {k: clean(str(item.get(k, '')), 500 if k == 'description' else 100)
               for k in ('id', 'order', 'item', 'material', 'description', 'quantity', 'unit', 'due')}
        if not all(row[k] for k in ('id','order','item','material','description','quantity')):
            raise ValueError('Cada item precisa de id, order, item, material, description e quantity.')
        if row['id'] in ids: raise ValueError('Identificador de item duplicado.')
        ids.add(row['id']); prepared.append(row)
    days = data.get('expiresInDays', 7)
    if type(days) is not int or not 1 <= days <= 30: raise ValueError('Validade entre 1 e 30 dias.')
    token, request_id = secrets.token_urlsafe(32), secrets.token_hex(12)
    expires = int(time.time()) + days * 86400
    with connect() as db:
        db.execute('INSERT INTO requests(id,token_hash,supplier,email,expires,items,created) VALUES(?,?,?,?,?,?,?)',
                   (request_id,digest(token),supplier,email,expires,json.dumps(prepared),int(time.time())))
    return {'id':request_id, 'url':BASE_URL + '/#token=' + token, 'expires':expires}

def validate_answers(data, items, complete):
    answers = data.get('answers')
    if not isinstance(answers, dict): raise ValueError('Respostas inválidas.')
    allowed = {i['id'] for i in items}
    if set(answers) - allowed: raise ValueError('Item não pertence a esta cobrança.')
    result = {}
    for item_id in allowed:
        a = answers.get(item_id, {})
        if not isinstance(a, dict): raise ValueError('Resposta inválida.')
        row = {k:clean(a.get(k,''), 2000 if k=='notes' else 100)
               for k in ('received','forecast','shipped','invoice','divergence','notes')}
        for key, options in [('received', ('','Sim','Não')),('shipped',('','Sim','Não','Parcialmente')),('divergence',('','Sim','Não'))]:
            if row[key] not in options: raise ValueError('Opção inválida.')
        if row['forecast']:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['forecast']): raise ValueError('Data inválida.')
            date.fromisoformat(row['forecast'])
        if complete:
            if not all(row[k] for k in ('received','shipped','divergence')):
                raise ValueError('Preencha recebido, enviado e divergência de todos os itens.')
            if row['divergence']=='Sim' and not row['notes']:
                raise ValueError('Descreva a divergência nas observações.')
        result[item_id] = row
    return result

class Handler(BaseHTTPRequestHandler):
    # Não registrar URLs, tokens ou corpos de requisições.
    def log_message(self, *_): pass
    def send(self, status, payload, content_type='application/json; charset=utf-8'):
        raw = json.dumps(payload,ensure_ascii=False).encode() if isinstance(payload,(dict,list)) else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers(); self.wfile.write(raw)
    def authorized_admin(self):
        value = self.headers.get('Authorization','')
        return bool(ADMIN_KEY) and hmac.compare_digest(value,'Bearer '+ADMIN_KEY)
    def supplier_request(self):
        value = self.headers.get('Authorization','')
        if not value.startswith('Bearer ') or len(value)>200: return None
        with connect() as db:
            return db.execute('SELECT * FROM requests WHERE token_hash=?',(digest(value[7:]),)).fetchone()
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health': return self.send(200,{'ok':True})
        if path == '/api/request':
            row = self.supplier_request()
            if not row: return self.send(404,{'error':'Link inválido.'})
            if row['expires'] <= time.time(): return self.send(410,{'error':'Este link expirou. Solicite uma nova cobrança ao comprador.'})
            return self.send(200, {'id':row['id'],'supplier':row['supplier'],'expires':row['expires'],
                       'items':json.loads(row['items']),'answers':json.loads(row['answers'] or '{}'),
                       'status':row['status'],'responder':row['responder'] or '', 'updated':row['updated']})
        if path.startswith('/api/admin/requests/'):
            if not self.authorized_admin(): return self.send(401,{'error':'Não autorizado.'})
            request_id = path.rsplit('/',1)[-1]
            with connect() as db: row=db.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
            if not row:return self.send(404,{'error':'Cobrança não encontrada.'})
            result={k:row[k] for k in ('id','supplier','email','status','expires','responder','updated','created')}
            result['items']=json.loads(row['items']); result['answers']=json.loads(row['answers'] or '{}')
            return self.send(200,result)
        files={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
        if path in files:
            mime={'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/styles.css':'text/css; charset=utf-8'}
            return self.send(200,(ROOT/'public'/files[path]).read_bytes(),mime[path])
        return self.send(404,{'error':'Não encontrado.'})
    def do_POST(self):
        try:
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                return self.send(415,{'error':'Use application/json.'})
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 2000000:return self.send(413,{'error':'Tamanho de requisição inválido.'})
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('JSON inválido.')
            path=urlsplit(self.path).path
            if path=='/api/admin/requests':
                if not self.authorized_admin():return self.send(401,{'error':'Não autorizado.'})
                return self.send(201,create_request(data))
            if path in ('/api/draft','/api/submit'):
                row=self.supplier_request()
                if not row:return self.send(404,{'error':'Link inválido.'})
                if row['expires']<=time.time():return self.send(410,{'error':'Link expirado.'})
                if row['status']=='submitted':return self.send(409,{'error':'Esta cobrança já foi respondida.'})
                complete=path=='/api/submit'
                answers=validate_answers(data,json.loads(row['items']),complete)
                responder=clean(data.get('responder',''),200)
                if complete and not responder:raise ValueError('Informe seu nome.')
                updated=int(time.time())
                with connect() as db:
                    changed=db.execute("UPDATE requests SET answers=?,responder=?,status=?,updated=? WHERE id=? AND status!='submitted' AND expires>?",
                        (json.dumps(answers),responder,'submitted' if complete else 'draft',updated,row['id'],updated)).rowcount
                if not changed:return self.send(409,{'error':'Cobrança encerrada ou expirada. Atualize a página.'})
                return self.send(200,{'ok':True,'status':'submitted' if complete else 'draft','updated':updated})
            return self.send(404,{'error':'Não encontrado.'})
        except (ValueError,TypeError,KeyError):return self.send(400,{'error':'Dados inválidos. Confira os campos, datas e observações de divergência.'})
        except Exception:return self.send(500,{'error':'Não foi possível salvar. Tente novamente.'})

if __name__=='__main__':
    if not ADMIN_KEY or len(ADMIN_KEY)<32:
        raise SystemExit('Configure ADMIN_API_KEY com pelo menos 32 caracteres aleatórios.')
    init_db()
    ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
