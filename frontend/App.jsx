import { useState, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Status machine ────────────────────────────────────────────────────────
const STEPS = [
  { id: "crawl",    label: "Crawling pages",        icon: "🔍" },
  { id: "analyze",  label: "Analyzing DOM & forms",  icon: "🧩" },
  { id: "generate", label: "Generating test cases",  icon: "🤖" },
  { id: "build",    label: "Building workbook",      icon: "📊" },
  { id: "done",     label: "Ready to download",      icon: "✅" },
];

export default function App() {
  const [url, setUrl]           = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showAuth, setShowAuth] = useState(false);
  const [phase, setPhase]       = useState("idle"); // idle | running | done | error
  const [stepIdx, setStepIdx]   = useState(0);
  const [error, setError]       = useState("");
  const [meta, setMeta]         = useState(null);   // { pages, sections, filename }
  const [downloadUrl, setDownloadUrl] = useState(null);
  const abortRef = useRef(null);
  const progressCardRef = useRef(null);

  const isRunning = phase === "running";

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;

    setPhase("running");
    setStepIdx(0);
    setError("");
    setMeta(null);
    setDownloadUrl(null);

    // Move focus to progress card for screen readers
    setTimeout(() => progressCardRef.current?.focus(), 50);

    // Simulate incremental progress steps while the real request runs
    const stepTimer = startStepTimer();

    try {
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      const fullUrl = url.trim().match(/^https?:\/\//) ? url.trim() : `https://${url.trim()}`;
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({
          url: fullUrl,
          username: username || null,
          password: password || null,
        }),
      });

      clearInterval(stepTimer);

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }

      // Extract metadata from response headers
      const pages    = res.headers.get("X-Pages-Crawled") || "?";
      const sections = res.headers.get("X-Sections-Generated") || "?";
      const disp     = res.headers.get("Content-Disposition") || "";
      const filename = disp.match(/filename="([^"]+)"/)?.[1] || "qa_suite.xlsx";

      // Trigger browser download
      const blob   = await res.blob();
      const objUrl = URL.createObjectURL(blob);

      setMeta({ pages, sections, filename });
      setDownloadUrl(objUrl);
      setStepIdx(STEPS.length - 1);
      setPhase("done");

    } catch (err) {
      clearInterval(stepTimer);
      if (err.name === "AbortError") return;
      setError(err.message || "Unexpected error");
      setPhase("error");
    }
  }

  function startStepTimer() {
    // Advance through steps 0-3 automatically while waiting
    const delays = [2000, 4000, 8000, 14000];
    let i = 0;
    return setInterval(() => {
      if (i < delays.length - 1) {
        i++;
        setStepIdx(i);
      }
    }, delays[i] || 3000);
  }

  function handleCancel() {
    abortRef.current?.abort();
    setPhase("idle");
    setStepIdx(0);
  }

  function handleReset() {
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    setPhase("idle");
    setStepIdx(0);
    setMeta(null);
    setDownloadUrl(null);
    setError("");
  }

  return (
    <div style={styles.root}>
      <div style={styles.bg} />
      <div style={styles.grain} />

      <main style={styles.main}>
        {/* ── Logo / heading ── */}
        <header style={styles.header}>
          <div style={styles.logo}>
            <svg width="42" height="42" viewBox="0 0 32 32" aria-hidden="true" style={styles.logoSvg}>
              <defs>
                <linearGradient id="lg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#9333EA" />
                  <stop offset="100%" stopColor="#6D28D9" />
                </linearGradient>
              </defs>
              <rect width="32" height="32" rx="8" fill="url(#lg)" />
              <path d="M8 16.5l5 5 11-11" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
            <h1 style={styles.logoText}>
              <span style={{ color: "#F0E6FF" }}>Suite</span>
              <span style={{ color: "#C084FC" }}>Gen</span>
            </h1>
          </div>
          <p style={styles.tagline}>
            Crawl any URL. Generate a structured, downloadable test suite — grounded in the actual UI.
          </p>
        </header>

        {/* ── Form card ── */}
        <div style={styles.card}>
          <form onSubmit={handleSubmit} style={styles.form} aria-busy={isRunning}>
            <div style={styles.urlRow}>
              <div style={styles.urlInputWrap}>
                <span style={styles.urlPrefix}>https://</span>
                <input
                  type="text"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="example.com"
                  style={styles.urlInput}
                  disabled={isRunning}
                  autoFocus
                  required
                  aria-label="Website URL to crawl"
                />
              </div>

              <button
                type="submit"
                disabled={isRunning || !url.trim()}
                style={{
                  ...styles.generateBtn,
                  ...(isRunning || !url.trim() ? styles.btnDisabled : {}),
                }}
              >
                {isRunning ? "Running…" : "Generate Suite"}
              </button>
            </div>

            {/* Auth toggle */}
            <button
              type="button"
              onClick={() => setShowAuth(v => !v)}
              style={styles.authToggle}
              disabled={isRunning}
              aria-expanded={showAuth}
            >
              {showAuth ? "▾" : "▸"} Auth credentials (optional)
            </button>

            {showAuth && (
              <div style={styles.authRow}>
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="Username"
                  style={styles.authInput}
                  disabled={isRunning}
                  autoComplete="username"
                  aria-label="HTTP basic auth username"
                />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Password"
                  style={styles.authInput}
                  disabled={isRunning}
                  autoComplete="current-password"
                  aria-label="HTTP basic auth password"
                />
              </div>
            )}
          </form>
        </div>

        {/* ── Progress ── */}
        {(isRunning || phase === "done") && (
          <div
            ref={progressCardRef}
            style={styles.progressCard}
            tabIndex={-1}
            role="status"
            aria-live="polite"
            aria-label="Generation progress"
          >
            <ol style={{ ...styles.steps, listStyle: "none", padding: 0, margin: 0 }}>
              {STEPS.map((step, i) => {
                const isDone    = i < stepIdx || phase === "done";
                const isActive  = i === stepIdx && isRunning;
                const isPending = i > stepIdx;

                return (
                  <li key={step.id} style={styles.stepRow}>
                    <div style={{
                      ...styles.stepDot,
                      ...(isDone  ? styles.stepDotDone    : {}),
                      ...(isActive ? styles.stepDotActive : {}),
                      ...(isPending ? styles.stepDotPending : {}),
                    }}>
                      {isDone ? "✓" : step.icon}
                    </div>
                    <span style={{
                      ...styles.stepLabel,
                      ...(isActive  ? { color: "#E2C4FF", fontWeight: 600 } : {}),
                      ...(isPending ? { color: "#777" } : {}),
                    }}>
                      {step.label}
                      {isActive && <Spinner />}
                    </span>
                  </li>
                );
              })}
            </ol>

            {isRunning && (
              <button onClick={handleCancel} style={styles.cancelBtn}>
                Cancel
              </button>
            )}
          </div>
        )}

        {/* ── Error ── */}
        {phase === "error" && (
          <div style={styles.errorCard} role="alert" aria-live="assertive">
            <span style={styles.errorIcon}>⚠</span>
            <div>
              <strong style={{ color: "#FF6B6B" }}>Something went wrong</strong>
              <p style={styles.errorText}>{error}</p>
            </div>
            <button onClick={handleReset} style={styles.retryBtn}>Try Again</button>
          </div>
        )}

        {/* ── Done / Download ── */}
        {phase === "done" && meta && downloadUrl && (
          <div style={styles.doneCard}>
            <div style={styles.doneStats}>
              <Stat label="Pages crawled"      value={meta.pages} />
              <Stat label="Test sections"      value={meta.sections} />
              <Stat label="Format"             value=".xlsx" />
            </div>

            <a
              href={downloadUrl}
              download={meta.filename}
              style={styles.downloadBtn}
            >
              ⬇ Download {meta.filename}
            </a>

            <button onClick={handleReset} style={styles.newBtn}>
              Generate another suite
            </button>
          </div>
        )}

        {/* ── How it works ── */}
        {phase === "idle" && (
          <div style={styles.howItWorks}>
            {[
              { icon: "🔍", title: "Deep Crawl",    desc: "Playwright maps every reachable page, capturing DOM structure, form fields, button labels, and API calls." },
              { icon: "🤖", title: "AI Generation", desc: "Claude generates test cases grounded in the actual UI — real field names, real interactions, real edge cases." },
              { icon: "📊", title: "Excel Output",  desc: "Formatted .xlsx with a Dashboard, per-section sheets, status dropdowns, priority tags, and color coding." },
            ].map(item => (
              <div key={item.title} style={styles.howCard}>
                <div style={styles.howIcon}>{item.icon}</div>
                <h2 style={styles.howTitle}>{item.title}</h2>
                <p style={styles.howDesc}>{item.desc}</p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={styles.stat} aria-label={`${label}: ${value}`}>
      <span style={styles.statValue}>{value}</span>
      <span style={styles.statLabel}>{label}</span>
    </div>
  );
}

function Spinner() {
  return <span style={styles.spinner} aria-hidden="true" />;
}

// ── Styles ─────────────────────────────────────────────────────────────────
const styles = {
  root: {
    minHeight: "100vh",
    backgroundColor: "#0C0C14",
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
    color: "#E8E8F0",
    position: "relative",
    overflow: "hidden",
  },
  bg: {
    position: "fixed",
    inset: 0,
    background: "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(130,60,200,0.18) 0%, transparent 70%), radial-gradient(ellipse 50% 40% at 80% 80%, rgba(40,100,200,0.12) 0%, transparent 60%)",
    pointerEvents: "none",
    zIndex: 0,
  },
  grain: {
    position: "fixed",
    inset: 0,
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E\")",
    pointerEvents: "none",
    zIndex: 0,
  },
  main: {
    position: "relative",
    zIndex: 1,
    maxWidth: 760,
    margin: "0 auto",
    padding: "64px 24px 80px",
  },
  header: {
    textAlign: "center",
    marginBottom: 40,
  },
  logo: {
    display: "inline-flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 16,
  },
  logoSvg: {
    filter: "drop-shadow(0 0 10px rgba(124,58,237,0.55))",
    flexShrink: 0,
  },
  logoText: {
    fontSize: 30,
    fontWeight: 700,
    letterSpacing: "-0.8px",
    margin: 0,
    lineHeight: 1,
  },
  tagline: {
    fontSize: 15,
    color: "#A0A0B4",
    maxWidth: 480,
    margin: "0 auto",
    lineHeight: 1.6,
  },

  // Card
  card: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 16,
    padding: "24px 28px",
    backdropFilter: "blur(12px)",
    marginBottom: 16,
  },
  form: { display: "flex", flexDirection: "column", gap: 12 },
  urlRow: { display: "flex", gap: 10, alignItems: "stretch" },
  urlInputWrap: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 10,
    overflow: "hidden",
  },
  urlPrefix: {
    padding: "0 10px",
    color: "#8A8A9A",
    fontSize: 13,
    whiteSpace: "nowrap",
    borderRight: "1px solid rgba(255,255,255,0.08)",
    height: "100%",
    display: "flex",
    alignItems: "center",
  },
  urlInput: {
    flex: 1,
    background: "transparent",
    border: "none",
    outline: "none",
    color: "#F0E6FF",
    fontSize: 14,
    padding: "12px 14px",
    fontFamily: "inherit",
  },
  generateBtn: {
    background: "linear-gradient(135deg, #7C3AED, #5B21B6)",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "0 24px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
    transition: "opacity 0.15s",
  },
  btnDisabled: { opacity: 0.4, cursor: "not-allowed" },
  authToggle: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: 12,
    cursor: "pointer",
    textAlign: "left",
    padding: 0,
    fontFamily: "inherit",
  },
  authRow: { display: "flex", gap: 10 },
  authInput: {
    flex: 1,
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.10)",
    borderRadius: 8,
    color: "#E0D8F0",
    padding: "9px 12px",
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
  },

  // Progress
  progressCard: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 14,
    padding: "22px 28px",
    marginBottom: 16,
  },
  steps: { display: "flex", flexDirection: "column", gap: 12 },
  stepRow: { display: "flex", alignItems: "center", gap: 14 },
  stepDot: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    flexShrink: 0,
    background: "rgba(255,255,255,0.06)",
    color: "#888",
    border: "1px solid rgba(255,255,255,0.1)",
  },
  stepDotDone: {
    background: "rgba(124,58,237,0.25)",
    color: "#C084FC",
    border: "1px solid rgba(192,132,252,0.4)",
  },
  stepDotActive: {
    background: "rgba(124,58,237,0.4)",
    color: "#E2C4FF",
    border: "1px solid #C084FC",
    boxShadow: "0 0 10px rgba(192,132,252,0.4)",
  },
  stepDotPending: { opacity: 0.3 },
  stepLabel: {
    fontSize: 13,
    color: "#999",
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  spinner: {
    display: "inline-block",
    width: 10,
    height: 10,
    borderRadius: "50%",
    border: "2px solid rgba(192,132,252,0.3)",
    borderTopColor: "#C084FC",
    animation: "spin 0.8s linear infinite",
  },
  cancelBtn: {
    marginTop: 16,
    background: "none",
    border: "1px solid rgba(255,100,100,0.3)",
    color: "#FF6B6B",
    borderRadius: 8,
    padding: "7px 16px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  },

  // Error
  errorCard: {
    display: "flex",
    alignItems: "flex-start",
    gap: 16,
    background: "rgba(255,80,80,0.08)",
    border: "1px solid rgba(255,80,80,0.2)",
    borderRadius: 14,
    padding: "20px 24px",
    marginBottom: 16,
  },
  errorIcon: { fontSize: 20, color: "#FF6B6B", flexShrink: 0 },
  errorText: { fontSize: 13, color: "#CC8080", margin: "4px 0 0" },
  retryBtn: {
    marginLeft: "auto",
    background: "rgba(255,80,80,0.15)",
    border: "1px solid rgba(255,80,80,0.3)",
    color: "#FF6B6B",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    alignSelf: "center",
  },

  // Done
  doneCard: {
    background: "rgba(124,58,237,0.08)",
    border: "1px solid rgba(192,132,252,0.25)",
    borderRadius: 16,
    padding: "24px 28px",
    marginBottom: 16,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 20,
  },
  doneStats: { display: "flex", gap: 32 },
  stat: { display: "flex", flexDirection: "column", alignItems: "center", gap: 2 },
  statValue: { fontSize: 24, fontWeight: 700, color: "#E2C4FF" },
  statLabel: { fontSize: 11, color: "#999", textTransform: "uppercase", letterSpacing: "0.05em" },
  downloadBtn: {
    display: "inline-block",
    background: "linear-gradient(135deg, #7C3AED, #5B21B6)",
    color: "#fff",
    borderRadius: 10,
    padding: "12px 28px",
    fontSize: 14,
    fontWeight: 600,
    textDecoration: "none",
    letterSpacing: "0.01em",
  },
  newBtn: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
  },

  // How it works
  howItWorks: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 14,
    marginTop: 32,
  },
  howCard: {
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 12,
    padding: "20px 18px",
  },
  howIcon: { fontSize: 22, marginBottom: 10 },
  howTitle: { fontSize: 13, fontWeight: 600, color: "#D0C0F0", margin: "0 0 6px" },
  howDesc: { fontSize: 12, color: "#999", lineHeight: 1.6, margin: 0 },
};

// Inject keyframes
const styleEl = document.createElement("style");
styleEl.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&display=swap');
  * { box-sizing: border-box; }
  body { margin: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
  }
`;
document.head.appendChild(styleEl);
