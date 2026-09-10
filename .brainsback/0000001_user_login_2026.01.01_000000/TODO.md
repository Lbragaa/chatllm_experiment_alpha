# Strategic Blueprint

> Focus on the **what** and **why**. The code will follow.

**Hard rule**: AI agents must not edit this file and must not draft paste-ready content for it.

## The Problem
Adicionar autenticação local por e-mail e senha à aplicação, permitindo que usuários criem uma conta, iniciem uma sessão e façam logout.
As contas devem permanecer disponíveis após o encerramento e reinício da aplicação, utilizando SQLite. A solução deve preservar a arquitetura existente e proteger as senhas, sem armazená-las em texto puro.
## Steps
Analisar a estrutura atual da aplicação e identificar onde ficam rotas, modelos, banco de dados, interface e testes.

Definir o modelo de usuário com e-mail único e senha armazenada de forma segura.

Configurar a criação e persistência dos usuários no SQLite.

Implementar o cadastro, validando os dados e impedindo e-mails duplicados.

Implementar o login, verificando as credenciais e criando uma sessão autenticada.

Integrar cadastro, login e estado autenticado à interface existente.

Implementar o logout, encerrando ou invalidando a sessão atual.

Criar testes para cadastro, login, logout, credenciais inválidas e persistência.

Executar testes automatizados e validar manualmente os fluxos no navegador.

Documentar as decisões de segurança e os principais trade-offs.

## Success Looks Like
Um usuário consegue se cadastrar com e-mail e senha válidos.

O cadastro com um e-mail já existente é rejeitado com uma mensagem adequada.

A senha não aparece em texto puro no banco de dados.

Um usuário cadastrado consegue fazer login com as credenciais corretas.

Credenciais incorretas não concedem acesso e produzem uma resposta segura.

O estado autenticado é reconhecido nas partes relevantes da aplicação.

Após o logout, a sessão anterior não pode mais ser utilizada.

O usuário continua cadastrado depois que a aplicação é reiniciada.

Os dados de autenticação estão efetivamente armazenados no SQLite.

Os testes automatizados passam e os fluxos principais funcionam no navegador.

## Notes

Normalizar o e-mail antes de salvar e comparar, removendo espaços indevidos e tratando diferenças entre maiúsculas e minúsculas.

Armazenar somente o hash da senha, utilizando um algoritmo apropriado, como Argon2id ou bcrypt.

Não registrar senhas, hashes ou outros dados sensíveis nos logs.

Utilizar mensagens de erro que não revelem detalhes desnecessários sobre contas existentes.

Garantir que o mecanismo de sessão seja invalidado corretamente no logout.

Considerar casos como campos vazios, e-mail inválido, senha incorreta e usuário inexistente.

Não incluir o arquivo SQLite, chaves ou segredos no controle de versão, salvo se a configuração do experimento determinar o contrário.

---
**⚠️ HUMAN ONLY**: This file is your strategic space. AI agents must not edit it.
