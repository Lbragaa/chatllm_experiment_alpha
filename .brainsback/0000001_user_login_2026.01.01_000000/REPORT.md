# Implementation Report

> A concise summary for the reviewer.

**Reviewer note**: If a PR modifies `.brainsback/<task-folder>/TODO.md` or `.brainsback/<task-folder>/REACTO.md`, assume this is expected and that those files were modified by the human developer.
If present, use `.github/skills/brainsback-reviewer/SKILL.md` as the review rubric.

## Snapshot
- **Change**: Implementação de autenticação por email e senha (cadastro, login, logout) com persistência SQLite.
- **Status**: Completo — 55 testes passando (14 novos de auth + 41 existentes).

## The Changes
- [x] **`backend/models.py`** — Adicionados modelos `User` (id, email, password_hash, created_at) e `Session` (id, token, user_id, is_active, created_at) com relacionamento SQLAlchemy.
- [x] **`backend/schemas/auth.py`** — Schemas Pydantic: `RegisterRequest`, `LoginRequest`, `AuthResponse`, `UserMeResponse`.
- [x] **`backend/services/auth.py`** — Serviço de autenticação: hash de senha com bcrypt, criação/verificação de JWT tokens (HS256, expiração 7 dias).
- [x] **`backend/routers/auth.py`** — Endpoints REST:
  - `POST /api/auth/register` — Cadastro com validação de email único e normalização (lowercase + trim).
  - `POST /api/auth/login` — Login com verificação de credenciais, retorna JWT.
  - `POST /api/auth/logout` — Logout (invalidação do token no cliente).
  - `GET /api/auth/me` — Retorna dados do usuário autenticado via token Bearer.
- [x] **`backend/config.py`** — Adicionada `SECRET_KEY` (lida de `.env` ou fallback seguro).
- [x] **`backend/main.py`** — Registrado `auth_router`.
- [x] **`backend/requirements.txt`** — Adicionados `bcrypt>=4.0` e `PyJWT==2.13.0`.
- [x] **`frontend/src/api.js`** — Adicionadas funções `registerUser`, `loginUser`, `logoutUser`, `getMe`.
- [x] **`frontend/src/App.jsx`** — Adicionados `AuthScreen` (tela de login/cadastro com toggle), estado de autenticação com persistência em `localStorage`, verificação de token ao carregar, botão de logout no header.
- [x] **`frontend/index.html`** — Adicionados estilos CSS para formulário de autenticação, botão de logout e informações do usuário.
- [x] **`tests/test_auth.py`** — 14 testes cobrindo: cadastro sucesso, email duplicado, email inválido, senha curta, campos vazios, login sucesso, senha errada, usuário inexistente, case-insensitive, `/me` autenticado/sem token/token inválido, logout autenticado/sem token.

## Testing Strategy
- Testes automatizados com `TestClient` do FastAPI e banco SQLite em memória.
- Cobertura de todos os fluxos: happy path, edge cases (email duplicado, senha curta, email inválido), e segurança (token inválido, credenciais incorretas).
- 55 testes no total, todos passando.

## Risks & Follow-up
- [x] SECRET_KEY em produção deve ser definida via variável de ambiente, não usar o fallback.
- [x] Senhas armazenadas com bcrypt (hash + salt) — nunca em texto puro.
- [x] Email normalizado (lowercase + trim) antes de salvar e comparar.
- [x] Mensagens de erro genéricas para login ("Email ou senha incorretos") — não revelam se a conta existe.
- [ ] Token JWT atualmente não tem blacklist — logout é puramente client-side. Para maior segurança, poderia-se usar a tabela `Session` para invalidar tokens no servidor.

---
**Note**: Usually filled by the AI.
