# Retorno Fornecedores

Portal em português para responder vários itens de pedidos em uma única tela, com integração por API ao Power Automate. Repositório privado; hospedagem não configurada automaticamente.

## O que já funciona

- Demonstração na página inicial com 3 itens fictícios e armazenamento local no navegador.
- Cobranças reais criadas pela API, com até 1.000 itens e validade configurável de 1 a 30 dias.
- Busca, filtros, paginação de 20 itens, seleção e aplicação de data em lote.
- Campos de recebimento, faturamento, envio, NF-e, divergência e observações.
- Rascunho salvo no servidor para cobranças reais; revisão e envio definitivo.
- Consulta de resultados por API administrativa para importação pelo Automate.
- Layout responsivo, labels acessíveis e confirmação antes do envio.
- SQLite persistente, hash do token no banco, validação de itens por cobrança, expiração e bloqueio após envio.

## Executar localmente

Requer Python 3.12 ou superior. Não há pacotes externos para instalar.

No terminal bash, dentro do projeto:

```bash
export ADMIN_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export PUBLIC_BASE_URL=http://localhost:8000
python server.py
```

Abra http://localhost:8000. Sem token, a página é uma demonstração; não envia dados a um comprador. Para reiniciar a demonstração, remova a chave `retorno-demo-v1` no armazenamento local do navegador.

A demonstração não substitui um teste da API: para criar uma cobrança real localmente, com o servidor executando, use outro terminal com a mesma variável `ADMIN_API_KEY`:

```bash
curl -X POST http://localhost:8000/api/admin/requests \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @docs/exemplo-cobranca.json
```

Abra o `url` retornado. A chave administrativa só deve existir no servidor e no conector seguro do Automate, nunca no HTML ou JavaScript do navegador.

## Hospedagem

O GitHub guarda o código. GitHub Pages, isoladamente, não executa este backend Python.

Use um servidor/container com HTTPS, disco persistente e suporte a Python. O Dockerfile está incluído. Configure as variáveis de `.env.example` pelo painel do provedor (o arquivo não é carregado automaticamente). Mantenha `/data` em um volume persistente e use apenas uma instância com esse banco SQLite.

A aplicação usa o servidor HTTP da biblioteca padrão para o protótipo. Antes de expor em produção, coloque-a atrás de um proxy HTTPS gerenciado, com limites de requisição, corpo e tempo de conexão. Para alta concorrência, evolua para servidor de aplicação e banco gerenciado apropriados. Não é um serviço pronto para escala ilimitada.

Não exponha o repositório nem altere sua visibilidade para publicar o site. São controles diferentes.

## Modelo de acesso

O link é uma credencial de acesso à cobrança. Quem tiver o link poderá acessar os itens até o vencimento; isto não comprova a identidade do fornecedor. O nome do responsável é declarado por ele. Para exigir identidade verificada, acrescente login ou código enviado por e-mail antes da produção.

O token aleatório é entregue uma vez na criação, colocado no fragmento `#token=` e enviado pelo cliente em `Authorization`. O servidor armazena só seu SHA-256. Não configure rastreadores na página nem registre cabeçalhos de autorização. O endpoint de consulta não revela e-mail nem token hash.

Rascunhos simultâneos usam a última gravação; para uso concorrente entre vários respondentes, adicione controle de versão. Após a resposta final, o link é somente leitura até expirar. Para corrigir, o comprador cria uma nova cobrança. A validade do link não apaga automaticamente os dados: defina retenção, backup e descarte com a empresa.

## Integração

Veja [o guia do Power Automate](docs/POWER_AUTOMATE.md). Nenhum fluxo foi criado na sua conta e nenhum e-mail é enviado automaticamente por este projeto.

## Verificação

```bash
python -m unittest discover -s tests -v
node --check public/app.js
```

Testes cobrem autorização, isolamento de cobranças, expiração, campos obrigatórios, datas inválidas, persistência de rascunho, envio final e bloqueio de reenvio. Não foi feito teste visual em navegador neste ambiente.
