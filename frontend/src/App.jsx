const { useEffect, useMemo, useRef, useState } = React;

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function AuthScreen({ onAuth }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const fn = isLogin ? loginUser : registerUser;
      const data = await fn({ email, password });
      localStorage.setItem("auth_token", data.token);
      onAuth(data.token, data.email);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand">ChatLLM Lab</div>
      </header>
      <div className="auth-container">
        <form className="auth-form" onSubmit={handleSubmit}>
          <h2>{isLogin ? "Entrar" : "Criar Conta"}</h2>
          {error && <div className="auth-error">{error}</div>}
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" required autoFocus />
          </label>
          <label>
            Senha
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="minimo 6 caracteres" required minLength={6} />
          </label>
          <button type="submit" disabled={loading}>{loading ? "Aguarde..." : isLogin ? "Entrar" : "Cadastrar"}</button>
          <p className="auth-toggle">
            {isLogin ? "Nao tem conta?" : "Ja tem conta?"}{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); setIsLogin(!isLogin); setError(""); }}>
              {isLogin ? "Cadastre-se" : "Faca login"}
            </a>
          </p>
        </form>
      </div>
    </main>
  );
}

function Sidebar({ sessions, activeSessionId, onSelectSession, onNewSession, onDeleteSession, userEmail, onLogout, busy }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={onNewSession} disabled={busy}>+ Nova conversa</button>
      </div>
      <div className="sidebar-sessions">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`sidebar-session ${s.id === activeSessionId ? "active" : ""}`}
            aria-disabled={busy}
            onClick={() => { if (!busy) onSelectSession(s.id); }}
          >
            <span className="session-title">{s.title || "Nova conversa"}</span>
            <button
              className="session-delete"
              disabled={busy}
              onClick={(e) => { e.stopPropagation(); onDeleteSession(s.id); }}
              title="Remover sessao"
            >&times;</button>
          </div>
        ))}
      </div>
      <div className="sidebar-footer">
        <span className="sidebar-email">{userEmail}</span>
        <button className="logout-btn" onClick={onLogout}>Sair</button>
      </div>
    </aside>
  );
}

function App() {
  const [token, setToken] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const [authLoading, setAuthLoading] = useState(true);

  // Sessions
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  // Messages
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const messagesRef = useRef(null);
  const abortControllerRef = useRef(null);
  const activeSessionRef = useRef(null);
  const operationRef = useRef(0);
  const submitLockRef = useRef(false);

  const chatHistory = useMemo(
    () => messages.filter((msg) => msg.role === "user" || msg.role === "assistant"),
    [messages]
  );

  // Load auth on mount
  useEffect(() => {
    let cancelled = false;
    const savedToken = localStorage.getItem("auth_token");
    if (savedToken) {
      getMe(savedToken).then((user) => {
        if (cancelled) return;
        if (user) {
          setToken(savedToken);
          setUserEmail(user.email);
        } else {
          localStorage.removeItem("auth_token");
        }
        setAuthLoading(false);
      }).catch((err) => {
        if (!cancelled) { setError(err.message); setAuthLoading(false); }
      });
    } else {
      setAuthLoading(false);
    }
    return () => { cancelled = true; };
  }, []);

  // Load sessions when token is set
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setSessionsLoading(true);
    listSessions(token).then((list) => {
      if (cancelled) return;
      setSessions(list);
      setSessionsLoading(false);
    }).catch((err) => {
      if (cancelled) return;
      setError(err.message);
      setSessionsLoading(false);
    });
    return () => { cancelled = true; };
  }, [token]);

  // Load messages when active session changes — skip while submitting
  useEffect(() => {
    let cancelled = false;
    activeSessionRef.current = activeSessionId;
    if (!token || !activeSessionId) {
      setMessages([]);
      return;
    }
    if (submitting) return;
    setMessages([]);
    getSessionMessages(token, activeSessionId).then((msgs) => {
      if (cancelled || activeSessionRef.current !== activeSessionId) return;
      if (msgs.length === 0) {
        setMessages([{ id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" }]);
      } else {
        setMessages(msgs.map((m) => ({ id: m.id, role: m.role, content: m.content })));
      }
    }).catch((err) => {
      if (cancelled || activeSessionRef.current !== activeSessionId) return;
      setError(err.message);
    });
    return () => { cancelled = true; };
  }, [token, activeSessionId, submitting]);

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);

  const onStop = () => {
    operationRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    submitLockRef.current = false;
    setBusy(false);
    setSubmitting(false);
  };

  const handleNewSession = async () => {
    if (submitLockRef.current) return;
    submitLockRef.current = true;
    setBusy(true);
    const operation = ++operationRef.current;
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      const session = await createSession(token, controller.signal);
      if (operationRef.current !== operation) return;
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
    } catch (err) {
      if (operationRef.current === operation && err.name !== "AbortError") setError(err.message);
    } finally {
      if (operationRef.current === operation) {
        submitLockRef.current = false;
        abortControllerRef.current = null;
        setBusy(false);
      }
    }
  };

  const handleSelectSession = (sessionId) => {
    if (submitLockRef.current) return;
    // Abort any ongoing stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setBusy(false);
    setActiveSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId) => {
    if (submitLockRef.current) return;
    const operation = ++operationRef.current;
    submitLockRef.current = true;
    // Abort any ongoing stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setBusy(true);
    try {
      await deleteSession(token, sessionId);
      if (operationRef.current !== operation) return;
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
    } catch (err) {
      if (operationRef.current === operation) setError(err.message);
    } finally {
      if (operationRef.current === operation) {
        submitLockRef.current = false;
        setBusy(false);
      }
    }
  };

  const refreshSessions = async (operation) => {
    if (!token) return;
    const list = await listSessions(token);
    if (operationRef.current === operation) setSessions(list);
  };

  const onSubmit = async (event, inputRef) => {
    event.preventDefault();
    const cleaned = text.trim();
    if (!cleaned || busy || submitLockRef.current) return;

    submitLockRef.current = true;
    const operation = ++operationRef.current;
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    setBusy(true);
    setError("");
    setSubmitting(true);

    // Auto-create session if none active
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      try {
        const session = await createSession(token, abortController.signal);
        if (operationRef.current !== operation) return;
        setSessions((prev) => [session, ...prev]);
        currentSessionId = session.id;
        setActiveSessionId(session.id);
      } catch (err) {
        if (operationRef.current !== operation) return;
        setError(err.message);
        setSubmitting(false);
        setBusy(false);
        submitLockRef.current = false;
        abortControllerRef.current = null;
        return;
      }
    }

    const userMessage = { id: createMessageId(), role: "user", content: cleaned };
    const assistantMessageId = createMessageId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);
    setText("");
    setBusy(true);

    try {
      const onDelta = (delta) => {
        if (operationRef.current !== operation) return;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: `${msg.content}${delta}` }
              : msg
          )
        );
      };

      await sendMessageStream({
        message: cleaned,
        history: chatHistory,
        sessionId: currentSessionId,
        token,
        signal: abortController.signal,
        onDelta,
      });

      if (operationRef.current !== operation) return;
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId && !msg.content.trim()
            ? { ...msg, content: "Nao foi possivel obter resposta do modelo agora." }
            : msg
        )
      );

      // Refresh sessions to get updated titles
      await refreshSessions(operation);
    } catch (err) {
      if (operationRef.current !== operation) return;
      const aborted = err?.name === "AbortError";
      if (!aborted) {
        setError(err.message || "Falha inesperada ao gerar resposta.");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: msg.content.trim() ? msg.content : "Nao foi possivel obter resposta do modelo agora." }
              : msg
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId && !msg.content.trim()
              ? { ...msg, content: "Resposta interrompida." }
              : msg
          )
        );
      }
    } finally {
      if (operationRef.current === operation) {
        abortControllerRef.current = null;
        submitLockRef.current = false;
        setBusy(false);
        setSubmitting(false);
      }
    }
  };

  const handleAuth = (newToken, email) => {
    setToken(newToken);
    setUserEmail(email);
  };

  const handleLogout = async () => {
    // Abort any ongoing stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    const operation = ++operationRef.current;
    submitLockRef.current = true;
    setBusy(true);
    try { await logoutUser(token); } catch (err) {
      if (operationRef.current === operation) {
        setError(err.message);
        submitLockRef.current = false;
        setSubmitting(false);
        setBusy(false);
      }
      return;
    }
    if (operationRef.current !== operation) return;
    localStorage.removeItem("auth_token");
    setToken(null);
    setUserEmail("");
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
    setText("");
    setError("");
    submitLockRef.current = false;
    setSubmitting(false);
    setBusy(false);
  };

  if (authLoading) {
    return (
      <main className="app-shell">
        <header className="app-header"><div className="brand">ChatLLM Lab</div></header>
        <div className="auth-container"><p>Carregando...</p></div>
      </main>
    );
  }

  if (!token) {
    return <AuthScreen onAuth={handleAuth} />;
  }

  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        userEmail={userEmail}
        onLogout={handleLogout}
        busy={busy}
      />
      <main className="app-main">
        <section className="messages" aria-live="polite" ref={messagesRef}>
          <div className="messages-inner">
            {messages.map((msg) => (
              <article key={msg.id} className={`bubble ${msg.role}`}>
                <MessageContent content={msg.content} />
              </article>
            ))}
          </div>
        </section>
        <Composer
          text={text}
          busy={busy}
          error={error}
          onChangeText={setText}
          onSubmit={onSubmit}
          onStop={onStop}
        />
        <div className="warning-banner">Lembre-se, voce precisa focar no experimento!!!</div>
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

