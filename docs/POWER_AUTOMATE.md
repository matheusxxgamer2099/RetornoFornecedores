# Conectar ao Power Automate

Pré-requisitos: backend hospedado com HTTPS e disco persistente, `PUBLIC_BASE_URL` definido, acesso à ação HTTP ou conector personalizado apropriado e licenciamento/políticas da empresa verificados. Este guia não cria um fluxo automaticamente.

## 1. Preparar a base

Excel em OneDrive corporativo ou SharePoint, dados em tabela `tbPedidos`. Colunas: `IdItem`, `FornecedorCodigo`, `FornecedorNome`, `FornecedorEmail`, `Pedido`, `Item`, `Material`, `Descricao`, `Quantidade`, `Unidade`, `DataLimiteEntrega`.

Identificadores e códigos devem ser texto. `IdItem` é único por linha. Não use número de material sozinho como chave. Datas enviadas à API são `AAAA-MM-DD`.

Crie uma lista interna `CobrancasEnviadas` com `RequestId` (texto), `FornecedorCodigo` (texto), `Status` (texto), `CriadoEm` (data), `ImportadoEm` (data). Guarde o link apenas se necessário, com acesso restrito: ele é uma credencial.

## 2. Fluxo manual para um fornecedor de teste

1. Criar fluxo da nuvem instantâneo → Disparar manualmente.
2. Excel Online (Business) → Listar linhas presentes em uma tabela → selecionar `tbPedidos`. Ativar paginação para bases maiores.
3. Filtrar matriz: selecionar somente o código do fornecedor de teste.
4. Operação de dados → Selecionar. Mapear as colunas para `id`, `order`, `item`, `material`, `description`, `quantity`, `unit`, `due`.
5. HTTP → POST → `https://SEU_DOMINIO/api/admin/requests`.
6. Headers: `Authorization: Bearer CHAVE_ADMINISTRATIVA` e `Content-Type: application/json`. Armazene a chave de acordo com a política da empresa. Ative entradas/saídas seguras nas ações que contêm a chave ou o link.
7. Corpo: usar o objeto abaixo; substituir `items` pela saída dinâmica de Selecionar, como array e não texto.

```json
{
  "supplier": "Fornecedor Exemplo Ltda.",
  "email": "seu-email-de-teste@example.com",
  "expiresInDays": 7,
  "items": []
}
```

Não envie `items` vazio: o exemplo só indica onde inserir o array da etapa 4. O arquivo `exemplo-cobranca.json` contém uma requisição completa para testar.

8. A resposta da API contém `id`, `url` e `expires` (Unix timestamp). Salve `id` em `CobrancasEnviadas` com status `Criada` antes do envio do e-mail.
9. Outlook → Enviar um e-mail (V2). Para: seu próprio e-mail no primeiro teste. Assunto: `Atualização dos pedidos`. No corpo HTML, inserir o `url` retornado como destino do botão/link `Responder pedidos`.
10. Após envio, atualizar o registro para `Enviada`. Se o e-mail falhar, reutilizar a cobrança existente; não criar outra cegamente.

A API cria um lote por chamada. Para todos os fornecedores, obtenha grupos únicos de código + destinatário, aplique um loop aos grupos, filtre suas linhas e repita o processo. Nunca envie a base inteira a um fornecedor. Controle o ritmo de envio conforme os limites do tenant. Máximo nesta versão: 1.000 itens por cobrança; divida volumes maiores em lotes.

## 3. Fluxo de importação de respostas

1. Gatilho Recorrência, conforme intervalo desejado.
2. Listar cobranças enviadas ainda não importadas.
3. Para cada `RequestId`, HTTP GET `https://SEU_DOMINIO/api/admin/requests/ID`, com o mesmo header administrativo e entradas/saídas seguras.
4. Se `status` não for `submitted`, seguir para a próxima cobrança.
5. Percorrer o array `items`. Para cada item, procurar `answers` pela chave `id` daquele item.
6. Atualizar a base usando o `IdItem` original, nunca a posição da linha. Respostas: `received`, `forecast`, `shipped`, `invoice`, `divergence`, `notes`.
7. Registrar o responsável (`responder`) e a data (`updated`, Unix timestamp).
8. Somente depois de todas as atualizações, marcar a cobrança como `Importada`.

Importação deve ser idempotente: repetir a mesma cobrança atualiza os mesmos itens sem duplicar registros. Se houver histórico, utilize chave única `RequestId + IdItem`. Não marque importada se alguma atualização falhar. Evite gravações concorrentes em um mesmo Excel.

## Endpoints

| Método | Caminho | Autorização | Finalidade |
|---|---|---|---|
| POST | `/api/admin/requests` | Bearer chave administrativa | Criar cobrança |
| GET | `/api/admin/requests/{id}` | Bearer chave administrativa | Consultar retorno |
| GET | `/api/request` | Bearer token da cobrança | Carregar itens |
| POST | `/api/draft` | Bearer token da cobrança | Salvar rascunho |
| POST | `/api/submit` | Bearer token da cobrança | Enviar resposta definitiva |

O fornecedor usa os três últimos endpoints pela própria página. Não disponibilize a chave administrativa ao fornecedor. Não coloque a URL secreta de um gatilho do Automate no JavaScript público.
