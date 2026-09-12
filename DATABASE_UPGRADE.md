# Atualização de autenticação e conversas

O servidor inicializa e verifica o SQLite ao iniciar. Importar `backend.main`
não cria tabelas e não altera o banco. Os testes usam `create_app(engine)` com
um SQLite temporário por teste e conexões independentes.

Se o banco ainda tiver `chat_messages.session_key`, a inicialização:

1. Cria uma cópia SQLite consistente em `database/chat.db.backup-<id>.sqlite`.
2. Renomeia a tabela antiga para `chat_messages_legacy`, preservando suas linhas.
3. Cria `chat_messages` com `session_id` e as demais tabelas que faltarem.

Usuários e conversas no esquema atual são preservados. Mensagens legadas não
tinham vínculo confiável com um usuário: ficam arquivadas, sem aparecer na
interface e sem serem atribuídas a uma conta arbitrária. Sua recuperação para
conversas atuais exige identificar os proprietários. A migração é transacional
e idempotente; um conflito com arquivo legado já existente interrompe a
inicialização com erro, sem apagar dados. Os backups não são versionados.

As sessões de autenticação agora são registradas no SQLite usando somente o
SHA-256 do JWT. Logout desativa a sessão atual; outros logins continuam válidos.
Tokens anteriores à atualização não têm registro e exigem novo login. Nenhuma
conta ou senha precisa ser recriada.

Durante envio ou criação de conversa, a sidebar bloqueia criar, selecionar e
excluir conversas. Use **Parar** antes de trocar. Logout cancela a requisição em
andamento e só limpa a autenticação após o servidor confirmar a revogação.
Uma resposta interrompida antes do salvamento não fica no histórico; a conversa
pode continuar vazia. Respostas completas são confirmadas apenas após commit.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
node --test tests/frontend_state.test.cjs
```

Os testes Node exercitam handlers reais e transporte SSE com requisições
controladas; não substituem uma conferência visual no navegador.
