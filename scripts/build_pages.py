"""Gera demonstração estática, sem conexão com o backend."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'_site'
out.mkdir(exist_ok=True)
html=(root/'public/index.html').read_text().replace('href="/styles.css"','href="./styles.css"').replace('src="/app.js"','src="./app.js"').replace('href="/"','href="./"')
html=html.replace('Dados fictícios. As respostas ficam somente neste navegador.','Teste no GitHub Pages • dados fictícios, sem envio ao comprador. As respostas ficam neste navegador.')
js=(root/'public/app.js').read_text().replace("const token=new URLSearchParams(location.hash.slice(1)).get('token');","const token=null; // GitHub Pages é exclusivamente demonstração local.")
(out/'index.html').write_text(html)
(out/'app.js').write_text(js)
(out/'styles.css').write_text((root/'public/styles.css').read_text())
(out/'.nojekyll').write_text('')
assert 'src="/app.js"' not in html
assert 'const token=null;' in js
print('Demonstração estática gerada em _site/')
