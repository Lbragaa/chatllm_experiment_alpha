# Implementation Report

## Estado atual — correções de 12/09/2026

Autenticação e sessões de chat corrigidas após a revisão. A implementação anterior
de logout somente no cliente foi substituída por revogação persistida no servidor.

## Alterações

- `backend/routers/auth.py` e `backend/models.py`: cadastro/login registram
  `AuthSession` com SHA-256 do JWT. A autenticação exige assinatura/expiração válidas,
  usuário existente e sessão ativa. Logout desativa apenas o token atual no SQLite.
- `backend/main.py` e `backend/database.py`: fábrica `create_app(engine)`, banco
  inicializado no lifespan e sessões por requisição. Importar a aplicação não altera
  o banco; testes injetam seu próprio engine antes da inicialização.
- `backend/migrations.py`: atualização idempotente do esquema legado, com backup
  SQLite e arquivamento de mensagens sem proprietário em `chat_messages_legacy`.
  Usuários e demais dados são preservados; não há `drop_all()` na aplicação.
- `backend/routers/chat.py`: streaming usa transação independente para salvar
  título, data e mensagens; o evento `done` é enviado somente após commit.
  Resposta vazia, conversa removida e falha de persistência geram erro.
- `frontend/src/App.jsx`: bloqueio imediato de envios duplicados, bloqueio da
  sidebar durante operações, cancelamento e descarte de callbacks antigos.
  Logout cancela o streaming e só limpa a autenticação após confirmação do servidor.
- `frontend/src/api.js`: criação cancelável e detecção de streaming encerrado
  sem confirmação de salvamento. JWT continua sendo enviado como Bearer.
- `tests/conftest.py`: SQLite em arquivo temporário por teste, NullPool,
  dependências reais e engines independentes para comprovar persistência.
- `DATABASE_UPGRADE.md`: procedimento de atualização, arquivo legado,
  necessidade de novo login e comportamento de cancelamento.

## Validação executada

- Python: **86 testes passando**, incluindo os testes existentes e regressões para
  revogação após reinício, preservação de usuários/mensagens legadas, idempotência,
  persistência do streaming com nova aplicação/engine e rollback de falha no commit.
- Node: **6 testes passando**, exercitando os handlers reais do frontend e o
  transporte SSE com requisições controladas: envio duplicado, troca durante stream,
  cancelamento, callbacks atrasados, logout e confirmação final de persistência.
- Exclusão em cascata verificada diretamente na tabela de mensagens.
- Nenhuma chamada real à OpenRouter é necessária para essas suítes.
- A execução utilizou bancos temporários; não foi iniciada a aplicação com
  `database/chat.db` para validar as alterações.
- Testes Node não renderizam a interface: validação visual no navegador ainda
  deve ser feita. Há avisos de depreciação das dependências Python.

## Comportamentos e limites

- Tokens emitidos antes desta atualização exigem novo login; contas são preservadas.
- Mensagens antigas sem usuário identificado permanecem no arquivo legado e no
  backup, fora da sidebar. Não se atribui esse histórico arbitrariamente a alguém.
- Interromper antes do salvamento descarta a resposta parcial; uma conversa vazia
  pode permanecer. Use Parar antes de trocar de conversa.
- Bcrypt, JWT HS256 com prazo de sete dias e localStorage permanecem. O fallback
  fixo de SECRET_KEY não é apropriado para produção; configure um segredo próprio.
- Os registros históricos de REACTO e revisão socrática não foram reescritos:
  descrevem a versão anterior, inclusive suas limitações de logout.
