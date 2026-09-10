# Socratic Review Record — Task 1: Login e Logout

> AI-generated. Humans must not create, edit, or pre-fill this file.

## Question 1 — Opening: What was implemented?

**Developer's answer:**
> Foi implementada autenticação local por e-mail e senha. O usuário pode se cadastrar, fazer login, consultar seus dados autenticados e fazer logout pela interface.
>
> No backend, os usuários são salvos no SQLite com senha protegida por hash bcrypt. O login gera um JWT, que o frontend guarda no `localStorage` para manter o estado autenticado. Também foram criados endpoints para cadastro, login, logout e consulta do usuário atual, além de testes automatizados para os fluxos principais.
>
> Uma limitação atual é que o logout remove o token somente do navegador; o JWT não é revogado no servidor e continua válido até expirar.

---

## Question 2 — Module Explanation

**Developer's answer:**
> O `App.jsx` controla a experiência do usuário no frontend. Quando a pessoa envia o formulário de cadastro ou login, ele chama as funções de comunicação da API, que enviam os dados para os endpoints de autenticação do backend.
>
> No backend, o `routers/auth.py` recebe a requisição HTTP. Ele usa os schemas de `schemas/auth.py` para validar o formato dos dados, como e-mail e senha. Depois, consulta ou cria um `User` definido em `models.py`, que representa os usuários persistidos no SQLite.
>
> No cadastro, o router encaminha a senha para as funções de `services/auth.py`, que geram o hash bcrypt antes de o usuário ser salvo. No login, o router busca o usuário pelo e-mail e chama o serviço para comparar a senha enviada com o hash armazenado. Se estiver correta, o serviço gera um JWT e o router devolve esse token ao frontend.
>
> O `App.jsx` recebe o JWT, salva-o no `localStorage` e atualiza a interface para o estado autenticado. Para consultar o usuário atual, o frontend envia o token ao endpoint correspondente; o backend valida esse JWT pelo serviço de autenticação antes de retornar os dados. No logout, o frontend chama o endpoint e remove o token do `localStorage`, voltando à tela de login.
>
> Em resumo, o fluxo é: `App.jsx` → API → `routers/auth.py` → schemas para validação + models para banco + services para senha/JWT → resposta ao `App.jsx`.

---

## Question 3 — Debugging Autonomy

**Developer's answer:**
> O JWT ainda passa pela validação de assinatura e expiração. Depois, `_get_current_user()` procura no SQLite o usuário indicado pelo campo `sub`. Como ele foi excluído, a consulta retorna `None` e o endpoint responde `401` com `"Usuario nao encontrado"`.
>
> No frontend, `getMe()` retorna `null`, o token é removido do `localStorage` e a tela de login é exibida. Para investigar, eu reproduziria o cenário, verificaria a resposta no navegador ou `TestClient` e acompanharia a execução de `_get_current_user()` com logs ou breakpoints. Como melhoria, usaria uma mensagem genérica de autenticação inválida e protegeria também os endpoints do chat.

---

## Question 4 — Logic Justification

**Developer's answer:**
> O `localStorage` foi escolhido pela simplicidade de implementação em uma aplicação acadêmica: o frontend consegue salvar o JWT e enviá-lo diretamente no cabeçalho `Authorization`. Porém, scripts executados por uma falha XSS podem acessar e roubar esse token.
>
> Cookies `HttpOnly` reduziriam esse risco porque não podem ser lidos pelo JavaScript, mas exigiriam configuração adicional de cookies, CORS e proteção contra CSRF. Para um sistema em produção, cookies `HttpOnly`, `Secure` e `SameSite` seriam uma alternativa mais segura.

---

## Question 5 — Onboarding Capability

**Developer's answer:**
> O formulário chama `api.js`, que envia as credenciais ao router do FastAPI. O router normaliza o e-mail, consulta o usuário no SQLite e usa o serviço de autenticação para verificar a senha com bcrypt. Se estiver correta, o backend gera um JWT e o frontend o salva no `localStorage`. Depois, `/api/auth/me` valida o token e consulta novamente o usuário no banco.
>
> Os schemas definem entradas e respostas, os models representam o banco, o service cuida de bcrypt e JWT, e o router coordena o fluxo. As regras principais são: e-mail único e normalizado, senha nunca armazenada diretamente e acesso autenticado dependente de token válido e usuário existente. As principais decisões foram usar bcrypt, JWT com expiração e `localStorage`, reconhecendo o risco de XSS e a ausência atual de revogação server-side.

---

## Question 6 — Closing: Satisfaction

**Developer's answer:**
> Estou satisfeito com o resultado para um projeto acadêmico, pois cadastro, login, persistência dos usuários e logout pela interface funcionam, com senhas protegidas por bcrypt e testes automatizados.
>
> Com mais tempo, implementaria revogação server-side para que o JWT deixasse de funcionar após o logout, protegeria também os endpoints do chat, usaria cookies `HttpOnly` no lugar de `localStorage`, exigiria uma `SECRET_KEY` segura e adicionaria rate limiting e testes reais de persistência após reiniciar a aplicação.

---

## Mastery Verdict

**Status: ✅ MASTERY DEMONSTRATED**

The developer demonstrated genuine understanding of the authentication implementation across all six dimensions:

1. **Scope (Q1):** Clearly articulated what was implemented and its limitations.
2. **Module Interaction (Q2):** Accurately traced the data flow from frontend to backend and back, naming specific modules and their responsibilities.
3. **Debugging (Q3):** Correctly traced the execution path for a user-deletion scenario, identified the root cause, and proposed a concrete investigation strategy.
4. **Design Justification (Q4):** Recognized the security trade-off of localStorage vs HttpOnly cookies and justified the choice within the academic context.
5. **Onboarding (Q5):** Demonstrated ability to communicate the architecture at a high level, covering data flow, module responsibilities, invariants, and design decisions.
6. **Self-Assessment (Q6):** Identified concrete, actionable improvements (server-side revocation, HttpOnly cookies, rate limiting, SECRET_KEY enforcement) that address the known limitations.

The developer consistently showed ownership of the code, acknowledged trade-offs honestly, and proposed meaningful improvements — meeting the criteria for mastery.