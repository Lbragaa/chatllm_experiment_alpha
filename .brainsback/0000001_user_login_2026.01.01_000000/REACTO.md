# Proof of Mastery (REACTO)

> Explain it to prove you own it.

**Hard rule**: AI agents must not edit this file and must not draft paste-ready content for it.

## R — Repeat (The Problem)
O objetivo foi adicionar autenticação local por e-mail e senha ao ChatLLM. O usuário deve conseguir se cadastrar, fazer login e fazer logout pela interface.

Os usuários são persistidos no SQLite. O estado autenticado no navegador é mantido por meio de um JWT salvo no localStorage. Embora exista um modelo Session, ele não é utilizado atualmente no fluxo de cadastro, login ou logout.

## E — Examples
Happy Path Input: Um usuário envia um e-mail ainda não cadastrado e uma senha válida para cadastro; em seguida, usa as mesmas credenciais no login.

Output: A conta é criada no banco, a senha é armazenada apenas como hash bcrypt e o login retorna um JWT válido. A interface identifica o usuário autenticado e exibe o botão de logout.

Edge Case Input: Um usuário tenta cadastrar um e-mail já existente ou realiza login com senha incorreta.

Output: A operação é recusada com uma resposta de erro adequada, sem autenticar o usuário e sem expor senha ou hash.

Logout Input: Um usuário autenticado aciona o logout.

Output: O frontend remove o JWT do localStorage e retorna à tela de login. O endpoint retorna sucesso, mas o JWT não é revogado no servidor; uma cópia do token continua válida até expirar.

## A — Approach
A solução separa responsabilidades entre frontend e backend. No backend, os schemas definem os dados de entrada e saída, o serviço de autenticação concentra hash de senha e JWT, e o router implementa as rotas HTTP e a normalização do e-mail.

O frontend consome esses endpoints, armazena o token no navegador e alterna entre a tela de autenticação e a aplicação autenticada. SQLite foi usado para persistir os usuários de forma simples no contexto da aplicação.
## C — Code
backend/models.py: define o modelo User, persistido com e-mail, hash de senha e restrição de unicidade. Também define Session, embora ela ainda não participe do fluxo de autenticação.

backend/schemas/auth.py: define as estruturas Pydantic de entrada e resposta para cadastro, login e dados do usuário.

backend/services/auth.py: concentra a criação e verificação de hashes bcrypt, além da geração e validação de JWTs.

backend/routers/auth.py: implementa os endpoints de cadastro, login, logout e consulta do usuário atual, incluindo a normalização do e-mail.

backend/config.py: define a SECRET_KEY usada para assinar os JWTs.

frontend/src/api.js: encapsula as chamadas de autenticação.

frontend/src/App.jsx: contém a tela de login/cadastro, armazena o JWT no localStorage e remove esse estado no logout.

A decisão central de segurança foi não armazenar senhas originais: somente o hash bcrypt é persistido e comparado durante o login.

## T — Tests

A validação automatizada foi feita em tests/test_auth.py, com 14 testes de autenticação. A suíte completa executou com sucesso: 55 testes passando, sendo 14 de autenticação e 41 já existentes.

Os testes cobrem os endpoints e cenários de autenticação, como cadastro, login, credenciais inválidas e resposta do logout. Eles usam SQLite em memória e desfazem alterações entre os testes; portanto, não comprovam que uma conta permanece cadastrada após reiniciar a aplicação.

O teste de logout verifica que o endpoint retorna 200 e a mensagem esperada, mas não verifica invalidação do token, pois o JWT continua válido no servidor até expirar. A validação manual no navegador deve ser registrada apenas depois de efetivamente executada.

## O — Optimize

A consulta por e-mail é beneficiada pelo índice da coluna, enquanto a restrição de unicidade impede o cadastro duplicado. Essas são responsabilidades diferentes: o índice melhora a busca e a restrição protege a consistência dos dados.

O bcrypt tem custo propositalmente maior que uma comparação comum de senha, pois dificulta ataques de força bruta. SQLite é adequado para o cenário local e acadêmico, mas uma aplicação com maior volume ou múltiplas instâncias poderia exigir um banco servidor.

A principal limitação atual é que a tabela Session está modelada, mas não é utilizada. O logout remove o token apenas no cliente: um JWT copiado permanece tecnicamente válido por até sete dias. Melhorias futuras incluem revogação server-side, rate limiting de tentativas de login, uso de cookies HttpOnly em vez de localStorage e obrigatoriedade de uma SECRET_KEY forte, sem fallback fixo, fora do ambiente acadêmico.