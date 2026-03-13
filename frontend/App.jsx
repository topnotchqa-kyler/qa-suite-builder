import { useState, useRef, useEffect } from "react";
import { supabase } from "./supabase.js";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Step definitions ──────────────────────────────────────────────────────────
const STEPS = [
  { id: "crawl",    label: "Crawl pages",        icon: "🔍" },
  { id: "generate", label: "Generate test cases", icon: "🤖" },
  { id: "done",     label: "Test suite ready",    icon: "✅" },
];

// ── Priority / category badge palette ─────────────────────────────────────────
const PRIORITY_STYLE = {
  Critical: { background: "rgba(69,10,10,0.85)",  color: "#fca5a5", border: "1px solid rgba(127,29,29,0.7)" },
  High:     { background: "rgba(67,20,7,0.85)",   color: "#fdba74", border: "1px solid rgba(124,45,18,0.7)" },
  Medium:   { background: "rgba(66,32,6,0.85)",   color: "#fcd34d", border: "1px solid rgba(113,63,18,0.7)" },
  Low:      { background: "rgba(30,41,59,0.85)",  color: "#94a3b8", border: "1px solid rgba(51,65,85,0.7)"  },
};
const CATEGORY_STYLE_BASE = { background: "rgba(15,34,49,0.85)", color: "#67e8f9", border: "1px solid rgba(22,78,99,0.7)" };

// ── Small shared components ───────────────────────────────────────────────────

function Badge({ children, extraStyle }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 7px",
      borderRadius: 4,
      fontSize: 10,
      fontWeight: 600,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
      whiteSpace: "nowrap",
      ...extraStyle,
    }}>
      {children}
    </span>
  );
}

function Spinner() {
  return <span style={styles.spinner} aria-hidden="true" />;
}

function Stat({ label, value }) {
  return (
    <div style={styles.stat}>
      <span style={styles.statValue}>{value}</span>
      <span style={styles.statLabel}>{label}</span>
    </div>
  );
}

function DetailField({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, color: "#B8B0CC", lineHeight: 1.55 }}>{value}</div>
    </div>
  );
}

// ── SiteArchitectureCard ──────────────────────────────────────────────────────

function SiteArchitectureCard({ crawlData }) {
  const arch = crawlData?.site_architecture;
  const pagesCrawled = crawlData?.pages_crawled || 0;
  const families = arch?.template_families || {};
  const familyEntries = Object.entries(families).sort((a, b) => b[1] - a[1]);

  return (
    <div style={styles.archCard}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <span style={{ color: "#86EFAC", fontSize: 13 }}>✓</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#D0C0F0" }}>Crawl Complete</span>
      </div>

      <div style={{ display: "flex", gap: 28, flexWrap: "wrap", marginBottom: familyEntries.length ? 18 : 0 }}>
        <Stat label="Pages crawled"  value={pagesCrawled} />
        {arch ? (
          <>
            <Stat label="URLs in sitemap" value={arch.total_urls_in_sitemap?.toLocaleString() || "—"} />
            <Stat label="Unique pages"    value={arch.unique_pages} />
            <Stat label="Discovery"       value={arch.discovery_method === "sitemap" ? "sitemap.xml" : "link-following"} />
          </>
        ) : (
          <Stat label="Discovery" value="link-following" />
        )}
      </div>

      {familyEntries.length > 0 && (
        <>
          <div style={{ fontSize: 11, color: "#555", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>
            Template Families
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
            {familyEntries.map(([key, count]) => (
              <div key={key} style={{
                background: "rgba(124,58,237,0.1)",
                border: "1px solid rgba(192,132,252,0.15)",
                borderRadius: 6,
                padding: "4px 10px",
                fontSize: 12,
                display: "flex",
                alignItems: "center",
                gap: 7,
              }}>
                <span style={{ color: "#9080BA" }}>{key}</span>
                <span style={{ color: "#C084FC", fontWeight: 700 }}>{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── TestCaseRow ───────────────────────────────────────────────────────────────

function TestCaseRow({ testCase, isLast, sectionIdx, testCaseIdx, editMode, onTestCaseChange }) {
  const [expanded, setExpanded] = useState(false);
  const steps = (testCase.steps || "").split("\n").filter(s => s.trim());
  const priorityStyle = PRIORITY_STYLE[testCase.priority] || PRIORITY_STYLE.Low;

  useEffect(() => {
    if (editMode) setExpanded(true);
  }, [editMode]);

  function onChange(field, value) {
    onTestCaseChange?.(sectionIdx, testCaseIdx, field, value);
  }

  return (
    <div style={{ borderBottom: isLast ? "none" : "1px solid rgba(255,255,255,0.03)" }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "9px 20px 9px 34px",
          background: expanded ? "rgba(255,255,255,0.03)" : "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "inherit",
          color: "inherit",
          transition: "background 0.1s",
        }}
        aria-expanded={expanded}
      >
        <Badge extraStyle={priorityStyle}>{testCase.priority}</Badge>
        <Badge extraStyle={CATEGORY_STYLE_BASE}>{testCase.category}</Badge>
        <span style={{ fontSize: 11, color: "#555", fontFamily: "monospace", flexShrink: 0 }}>
          {testCase.id}
        </span>
        {editMode ? (
          <input
            type="text"
            value={testCase.title || ""}
            onChange={e => onChange("title", e.target.value)}
            onClick={e => e.stopPropagation()}
            style={styles.editInput}
            placeholder="Test case title"
          />
        ) : (
          <span style={{ flex: 1, fontSize: 13, color: "#C8C0D8", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {testCase.title}
          </span>
        )}
        <span style={{ color: "#444", fontSize: 9, flexShrink: 0, marginLeft: 4 }}>
          {expanded ? "▲" : "▶"}
        </span>
      </button>

      {expanded && (
        <div style={{
          padding: "6px 20px 16px 34px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
          background: "rgba(255,255,255,0.015)",
        }}>
          {editMode ? (
            <>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Priority</div>
                <select value={testCase.priority || "Medium"} onChange={e => onChange("priority", e.target.value)} style={styles.editSelect}>
                  {["Critical", "High", "Medium", "Low"].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Category</div>
                <input type="text" value={testCase.category || ""} onChange={e => onChange("category", e.target.value)} style={styles.editInput} placeholder="e.g. Functional" />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Description</div>
                <textarea rows={3} value={testCase.description || ""} onChange={e => onChange("description", e.target.value)} style={styles.editTextarea} placeholder="Describe the test case..." />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Preconditions</div>
                <textarea rows={2} value={testCase.preconditions || ""} onChange={e => onChange("preconditions", e.target.value)} style={styles.editTextarea} placeholder="Preconditions..." />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Steps</div>
                <textarea rows={5} value={testCase.steps || ""} onChange={e => onChange("steps", e.target.value)} style={styles.editTextarea} placeholder={"1. Step one\n2. Step two"} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Expected Result</div>
                <textarea rows={2} value={testCase.expected_result || ""} onChange={e => onChange("expected_result", e.target.value)} style={styles.editTextarea} placeholder="Expected result..." />
              </div>
            </>
          ) : (
            <>
              {testCase.description && (
                <DetailField label="Description" value={testCase.description} />
              )}
              {testCase.preconditions && (
                <DetailField label="Preconditions" value={testCase.preconditions} />
              )}
              {steps.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: "#777", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                    Steps
                  </div>
                  <ol style={{ margin: 0, paddingLeft: 20 }}>
                    {steps.map((step, i) => (
                      <li key={i} style={{ fontSize: 13, color: "#B8B0CC", marginBottom: 4, lineHeight: 1.55 }}>
                        {step.replace(/^\d+\.\s*/, "")}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {testCase.expected_result && (
                <DetailField label="Expected Result" value={testCase.expected_result} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── SectionCard ───────────────────────────────────────────────────────────────

function SectionCard({ section, defaultExpanded, isLast, sectionIdx, editMode, onTestCaseChange }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const tests = section.test_cases || [];

  return (
    <div style={{ borderBottom: isLast ? "none" : "1px solid rgba(255,255,255,0.05)" }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "13px 20px",
          background: expanded ? "rgba(124,58,237,0.05)" : "rgba(255,255,255,0.01)",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          fontFamily: "inherit",
          color: "inherit",
          transition: "background 0.15s",
        }}
        aria-expanded={expanded}
      >
        <span style={{ color: "#7C3AED", fontSize: 9, flexShrink: 0, marginTop: 1 }}>
          {expanded ? "▼" : "▶"}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#D0C0F0", marginBottom: 2 }}>
            {section.name}
          </div>
          <div style={{ fontSize: 11, color: "#555", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {section.source_url}
          </div>
        </div>
        <span style={{
          fontSize: 11,
          color: "#7777AA",
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 5,
          padding: "2px 9px",
          flexShrink: 0,
        }}>
          {tests.length} test{tests.length !== 1 ? "s" : ""}
        </span>
      </button>

      {expanded && tests.length > 0 && (
        <div style={{ paddingBottom: 4 }}>
          {tests.map((tc, i) => (
            <TestCaseRow
              key={tc.id || i}
              testCase={tc}
              isLast={i === tests.length - 1}
              sectionIdx={sectionIdx}
              testCaseIdx={i}
              editMode={editMode}
              onTestCaseChange={onTestCaseChange}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── TestSuiteViewer ───────────────────────────────────────────────────────────

function TestSuiteViewer({
  testSuite, crawlData, onDownloadXlsx, isDownloading, suiteId, onCopyLink, linkCopied,
  canEdit, editMode, editedSuite, isSaving, saveError, onEnterEdit, onCancelEdit, onSaveEdit, onTestCaseChange,
}) {
  const activeSuite = editMode ? editedSuite : testSuite;
  const totalTests = (activeSuite.sections || []).reduce((sum, s) => sum + (s.test_cases || []).length, 0);

  return (
    <div style={{ marginBottom: 16 }}>
      {/* Header */}
      <div style={{
        background: "rgba(124,58,237,0.08)",
        border: "1px solid rgba(192,132,252,0.2)",
        borderRadius: "14px 14px 0 0",
        padding: "20px 24px",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 16,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: "#E2C4FF", margin: "0 0 5px" }}>
            {activeSuite.site_name} — Test Suite
          </h2>
          <div style={{ fontSize: 12, color: "#7777AA", marginBottom: activeSuite.summary ? 10 : 0 }}>
            {crawlData?.pages_crawled} page{crawlData?.pages_crawled !== 1 ? "s" : ""} crawled
            &nbsp;·&nbsp;{(activeSuite.sections || []).length} sections
            &nbsp;·&nbsp;{totalTests} test cases
          </div>
          {activeSuite.summary && (
            <p style={{ fontSize: 13, color: "#9090A8", margin: 0, lineHeight: 1.55, maxWidth: 560 }}>
              {activeSuite.summary}
            </p>
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end", flexShrink: 0 }}>
          {/* Edit mode controls */}
          {canEdit && !editMode && (
            <button onClick={onEnterEdit} style={styles.editBtn}>✏ Edit</button>
          )}
          {editMode && (
            <>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={onSaveEdit} disabled={isSaving} style={{ ...styles.saveBtn, opacity: isSaving ? 0.6 : 1, cursor: isSaving ? "not-allowed" : "pointer" }}>
                  {isSaving ? "Saving…" : "Save changes"}
                </button>
                <button onClick={onCancelEdit} disabled={isSaving} style={styles.cancelEditBtn}>
                  Cancel
                </button>
              </div>
              {saveError && (
                <p style={{ fontSize: 11, color: "#FF8080", margin: 0, textAlign: "right" }}>{saveError}</p>
              )}
            </>
          )}
          {/* Download / copy link (hidden in edit mode) */}
          {!editMode && (
            <>
              <button
                onClick={onDownloadXlsx}
                disabled={isDownloading}
                style={{
                  background: isDownloading ? "rgba(124,58,237,0.2)" : "linear-gradient(135deg,#7C3AED,#5B21B6)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 9,
                  padding: "10px 18px",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: isDownloading ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                  opacity: isDownloading ? 0.6 : 1,
                  fontFamily: "inherit",
                  transition: "opacity 0.15s",
                }}
              >
                {isDownloading ? "Preparing…" : "⬇ Download .xlsx"}
              </button>
              {suiteId && (
                <button
                  onClick={onCopyLink}
                  style={{
                    background: "none",
                    border: "1px solid rgba(192,132,252,0.25)",
                    borderRadius: 7,
                    padding: "6px 12px",
                    fontSize: 11,
                    color: linkCopied ? "#86EFAC" : "#9070C0",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    whiteSpace: "nowrap",
                    transition: "color 0.15s",
                  }}
                >
                  {linkCopied ? "✓ Link copied" : "🔗 Copy link"}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Sections */}
      <div style={{
        border: "1px solid rgba(192,132,252,0.2)",
        borderTop: "none",
        borderRadius: "0 0 14px 14px",
        overflow: "hidden",
      }}>
        {(activeSuite.sections || []).map((section, i) => (
          <SectionCard
            key={section.source_url || i}
            section={section}
            defaultExpanded={i === 0}
            isLast={i === activeSuite.sections.length - 1}
            sectionIdx={i}
            editMode={editMode}
            onTestCaseChange={onTestCaseChange}
          />
        ))}
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

function Dashboard({ suites, loading, error, onOpen, onNavigateHome }) {
  return (
    <div style={styles.dashboardWrap}>
      <div style={styles.dashboardHeader}>
        <button onClick={onNavigateHome} style={styles.dashboardBackBtn}>← Back</button>
        <h2 style={styles.dashboardTitle}>My Test Suites</h2>
      </div>

      {loading && (
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div style={styles.errorCard} role="alert">
          <span style={styles.errorIcon}>⚠</span>
          <div style={{ flex: 1 }}>
            <strong style={{ color: "#FF6B6B" }}>Could not load suites</strong>
            <p style={styles.errorText}>{error}</p>
          </div>
        </div>
      )}

      {!loading && !error && suites !== null && suites.length === 0 && (
        <div style={{ textAlign: "center", padding: "60px 24px", color: "#666" }}>
          <p style={{ fontSize: 15, margin: "0 0 16px" }}>No suites yet — generate your first test suite.</p>
          <button
            onClick={onNavigateHome}
            style={{ background: "linear-gradient(135deg,#7C3AED,#5B21B6)", color: "#fff", border: "none", borderRadius: 9, padding: "10px 24px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            Generate a Suite →
          </button>
        </div>
      )}

      {!loading && !error && suites && suites.length > 0 && (
        <div style={styles.dashboardTable}>
          {suites.map((s, idx) => (
            <div key={s.id} style={{ ...styles.dashboardRow, borderBottom: idx === suites.length - 1 ? "none" : "1px solid rgba(255,255,255,0.05)" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={styles.dashboardSiteName}>{s.site_name || "Untitled"}</div>
                <div style={styles.dashboardMeta}>{s.base_url}</div>
              </div>
              <div style={styles.dashboardDate}>
                {new Date(s.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <button onClick={() => onOpen(s.id)} style={styles.dashboardActionBtn}>Open</button>
              <a href={`${API_BASE}/api/suites/${s.id}/xlsx`} download style={styles.dashboardDownloadLink}>
                ⬇ xlsx
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Auth icon helpers ─────────────────────────────────────────────────────────

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.604-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
  );
}

// ── Auth modal ────────────────────────────────────────────────────────────────

function AuthModal({ mode, onModeChange, onClose, onSuccess }) {
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState({ text: "", isError: false });
  const [loading, setLoading] = useState(false);

  async function handleEmailSubmit(e) {
    e.preventDefault();
    if (!supabase) return;
    setMessage({ text: "", isError: false });
    setLoading(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setMessage({ text: "Check your email to confirm your account.", isError: false });
        // Don't close — user must confirm email first
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        onSuccess();
      }
    } catch (err) {
      setMessage({ text: err.message || "Authentication failed.", isError: true });
    } finally {
      setLoading(false);
    }
  }

  async function handleOAuth(provider) {
    if (!supabase) return;
    setMessage({ text: "", isError: false });
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: window.location.origin },
      });
      if (error) throw error;
      // Browser navigates away — no further action needed
    } catch (err) {
      setMessage({ text: err.message || `${provider} sign-in failed.`, isError: true });
      setLoading(false);
    }
  }

  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={styles.modalPanel} onClick={e => e.stopPropagation()}>
        {/* Tab switcher */}
        <div style={styles.authTabs}>
          {[["signin", "Sign in"], ["signup", "Sign up"]].map(([m, label]) => (
            <button
              key={m}
              onClick={() => { onModeChange(m); setMessage({ text: "", isError: false }); }}
              style={{ ...styles.authTab, ...(mode === m ? styles.authTabActive : {}) }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* OAuth buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button onClick={() => handleOAuth("google")} disabled={loading} style={styles.oauthBtn}>
            <GoogleIcon /> Continue with Google
          </button>
          <button onClick={() => handleOAuth("github")} disabled={loading} style={styles.oauthBtn}>
            <GitHubIcon /> Continue with GitHub
          </button>
        </div>

        {/* Divider */}
        <div style={styles.orDivider}>
          <span style={styles.orDividerLine} />
          <span style={styles.orDividerText}>or</span>
          <span style={styles.orDividerLine} />
        </div>

        {/* Email / password form */}
        <form onSubmit={handleEmailSubmit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="Email"
            required
            style={styles.authInput}
            autoComplete="email"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            required
            style={styles.authInput}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
          />

          {message.text && (
            <p style={{ fontSize: 12, color: message.isError ? "#FF8080" : "#86EFAC", margin: 0, lineHeight: 1.5 }}>
              {message.text}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.generateBtn, padding: "11px", opacity: loading ? 0.6 : 1, cursor: loading ? "not-allowed" : "pointer" }}
          >
            {loading ? "…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  // ── Auth state ──────────────────────────────────────────────────────────────
  const [user, setUser]               = useState(null);   // Supabase User or null
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode]       = useState("signin"); // "signin"|"signup"

  // ── App state ───────────────────────────────────────────────────────────────
  const [url, setUrl]           = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showAuth, setShowAuth] = useState(false);
  const [apiKey, setApiKey]     = useState("");
  const [phase, setPhase]       = useState("idle"); // idle|crawling|crawled|generating|done|error
  const [error, setError]       = useState("");
  const [submittedUrl, setSubmittedUrl] = useState(""); // URL shown during active phases
  const [crawlData, setCrawlData]       = useState(null);
  const [testSuiteData, setTestSuiteData] = useState(null);
  const [suiteId, setSuiteId]             = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [linkCopied, setLinkCopied]       = useState(false);
  const abortRef = useRef(null);

  // ── Routing state ────────────────────────────────────────────────────────────
  const [currentPage, setCurrentPage] = useState("home"); // "home" | "dashboard"

  // ── Dashboard state ──────────────────────────────────────────────────────────
  const [dashboardSuites, setDashboardSuites] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError]   = useState("");

  // ── Edit mode state ──────────────────────────────────────────────────────────
  const [editMode, setEditMode]       = useState(false);
  const [editedSuite, setEditedSuite] = useState(null);
  const [suiteOwnerId, setSuiteOwnerId] = useState(null);
  const [isSaving, setIsSaving]       = useState(false);
  const [saveError, setSaveError]     = useState("");

  // ── Supabase auth listener (runs before suite loader — order matters) ────────
  useEffect(() => {
    if (!supabase) return;

    // Exchange PKCE code from OAuth redirect, then set user from session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      // Remove ?code= from the URL so it doesn't interfere with ?suite= logic
      if (window.location.search.includes("code=")) {
        window.history.replaceState({}, "", window.location.pathname);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Load shared suite from ?suite=<id> on first render ───────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sharedId = params.get("suite");
    if (!sharedId) return;

    setPhase("generating"); // reuse spinner while loading
    fetch(`${API_BASE}/api/suites/${sharedId}`)
      .then(res => {
        if (!res.ok) throw new Error("Suite not found");
        return res.json();
      })
      .then(data => {
        setCrawlData(data.crawl_data);
        setTestSuiteData(data.test_suite);
        setSubmittedUrl(data.base_url || "");
        setSuiteId(sharedId);
        setSuiteOwnerId(data.user_id || null);
        setPhase("done");
      })
      .catch(() => {
        setError("Could not load the shared suite. The link may be invalid or expired.");
        setPhase("error");
        window.history.replaceState({}, "", "/");
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Client-side routing (no react-router) ────────────────────────────────────
  useEffect(() => {
    if (window.location.pathname === "/dashboard") setCurrentPage("dashboard");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    function onPopState() {
      setCurrentPage(window.location.pathname === "/dashboard" ? "dashboard" : "home");
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const isActive = phase === "crawling" || phase === "generating";

  // Derive step states from phase
  const stepStates = [
    // step 0: crawl
    ["crawled", "generating", "done"].includes(phase) ? "done"
      : phase === "crawling" ? "active"
      : "pending",
    // step 1: generate
    phase === "done" ? "done"
      : phase === "generating" ? "active"
      : "pending",
    // step 2: ready
    phase === "done" ? "done" : "pending",
  ];

  // ── Handlers ────────────────────────────────────────────────────────────────

  // Returns { Authorization: "Bearer <token>" } when signed in, otherwise {}
  async function getAuthHeaders() {
    if (!supabase) return {};
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ? { "Authorization": `Bearer ${session.access_token}` } : {};
  }

  function handleCopyLink() {
    const url = `${window.location.origin}/?suite=${suiteId}`;
    navigator.clipboard.writeText(url).then(() => {
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    });
  }

  async function handleCrawl(e) {
    e.preventDefault();
    if (!url.trim()) return;

    const fullUrl = url.trim().match(/^https?:\/\//) ? url.trim() : `https://${url.trim()}`;
    setSubmittedUrl(fullUrl);
    setPhase("crawling");
    setCrawlData(null);
    setTestSuiteData(null);
    setError("");

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(`${API_BASE}/api/crawl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({ url: fullUrl, username: username || null, password: password || null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      if (!data.pages || data.pages.length === 0) {
        throw new Error("No pages were crawled. Check the URL and try again.");
      }
      setCrawlData(data);
      setPhase("crawled");
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || "Crawl failed. Check the URL and try again.");
      setPhase("error");
    }
  }

  async function handleGenerate() {
    setPhase("generating");
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const authHeaders = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/generate-from-crawl?format=json`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiKey ? { "X-Api-Key": apiKey } : {}),
          ...authHeaders,
        },
        signal: ctrl.signal,
        body: JSON.stringify(crawlData),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setTestSuiteData(data.test_suite);
      if (data.suite_id) {
        setSuiteId(data.suite_id);
        setSuiteOwnerId(user?.id || null);
        window.history.pushState({}, "", `/?suite=${data.suite_id}`);
      }
      setPhase("done");
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message || "Generation failed. Please try again.");
      setPhase("error");
    }
  }

  async function handleDownloadXlsx() {
    if (isDownloading) return;
    setIsDownloading(true);
    try {
      // If we have a saved suite ID, download directly — no AI call needed
      const authHeaders = await getAuthHeaders();
      const res = suiteId
        ? await fetch(`${API_BASE}/api/suites/${suiteId}/xlsx`)
        : await fetch(`${API_BASE}/api/generate-from-crawl`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(apiKey ? { "X-Api-Key": apiKey } : {}),
              ...authHeaders,
            },
            body: JSON.stringify(crawlData),
          });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${res.status}`);
      }
      const disp = res.headers.get("Content-Disposition") || "";
      const filename = disp.match(/filename="([^"]+)"/)?.[1] || "qa_suite.xlsx";
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(objUrl), 60000);
    } catch (err) {
      // Non-destructive: keep test suite visible, show a brief alert
      alert(`Download failed: ${err.message}`);
    } finally {
      setIsDownloading(false);
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
    setPhase("idle");
  }

  function handleReset() {
    abortRef.current?.abort();
    setPhase("idle");
    setCrawlData(null);
    setTestSuiteData(null);
    setSuiteId(null);
    setError("");
    setIsDownloading(false);
    setSubmittedUrl("");
    setLinkCopied(false);
    setEditMode(false);
    setEditedSuite(null);
    setSuiteOwnerId(null);
    setSaveError("");
    window.history.replaceState({}, "", "/");
  }

  // ── Navigation ───────────────────────────────────────────────────────────────

  function navigateTo(page) {
    if (page === "dashboard") {
      window.history.pushState({}, "", "/dashboard");
      setCurrentPage("dashboard");
      if (phase !== "idle") handleReset();
    } else {
      window.history.pushState({}, "", "/");
      setCurrentPage("home");
    }
  }

  // ── Dashboard loader ─────────────────────────────────────────────────────────

  async function loadDashboard() {
    if (!supabase || !user) return;
    setDashboardLoading(true);
    setDashboardError("");
    try {
      const authHeaders = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/suites`, { headers: authHeaders });
      if (res.status === 401) { setDashboardError("Please sign in to view your dashboard."); return; }
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setDashboardSuites(data.suites || []);
    } catch (err) {
      setDashboardError(err.message || "Could not load suites.");
    } finally {
      setDashboardLoading(false);
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (currentPage === "dashboard" && user) loadDashboard(); }, [currentPage, user]);

  // ── Open suite from dashboard ─────────────────────────────────────────────────

  async function handleOpenSuite(id) {
    navigateTo("home");
    setPhase("generating");
    try {
      const res = await fetch(`${API_BASE}/api/suites/${id}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setCrawlData(data.crawl_data);
      setTestSuiteData(data.test_suite);
      setSubmittedUrl(data.base_url || "");
      setSuiteId(id);
      setSuiteOwnerId(data.user_id || null);
      setPhase("done");
      window.history.pushState({}, "", `/?suite=${id}`);
    } catch {
      setError("Could not load the suite.");
      setPhase("error");
    }
  }

  // ── Edit mode handlers ───────────────────────────────────────────────────────

  function handleEnterEdit() {
    setEditedSuite(JSON.parse(JSON.stringify(testSuiteData)));
    setEditMode(true);
    setSaveError("");
  }

  function handleCancelEdit() {
    setEditedSuite(null);
    setEditMode(false);
    setSaveError("");
  }

  async function handleSaveEdit() {
    if (!suiteId || !editedSuite) return;
    setIsSaving(true);
    setSaveError("");
    try {
      const authHeaders = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/suites/${suiteId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ test_suite: editedSuite }),
      });
      if (res.status === 403) throw new Error("You don't have permission to edit this suite.");
      if (res.status === 401) throw new Error("Please sign in to save changes.");
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || `Error ${res.status}`); }
      setTestSuiteData(editedSuite);
      setEditedSuite(null);
      setEditMode(false);
    } catch (err) {
      setSaveError(err.message || "Save failed. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  function handleTestCaseChange(sectionIdx, caseIdx, field, value) {
    setEditedSuite(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next.sections[sectionIdx].test_cases[caseIdx][field] = value;
      return next;
    });
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div style={styles.root}>
      <div style={styles.bg} />
      <div style={styles.grain} />

      {/* GitHub link */}
      <a
        href="https://github.com/topnotchqa-kyler/qa-suite-builder"
        target="_blank"
        rel="noopener noreferrer"
        style={styles.githubLink}
        className="sg-github"
        aria-label="View source on GitHub"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
          <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.604-3.369-1.342-3.369-1.342-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.579.688.481C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
        </svg>
        <span>GitHub</span>
      </a>

      {/* Auth: user pill (signed in) */}
      {supabase && user && (
        <div style={styles.userPill} className="sg-auth-btn">
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>
            {user.email}
          </span>
          <button
            onClick={() => supabase.auth.signOut()}
            style={{ background: "none", border: "none", color: "#7C5EA0", fontSize: 11, cursor: "pointer", fontFamily: "inherit", padding: 0, marginLeft: 4, whiteSpace: "nowrap" }}
          >
            Sign out
          </button>
        </div>
      )}

      {/* Auth: sign-in button (signed out) */}
      {supabase && !user && (
        <button
          className="sg-auth-btn"
          onClick={() => { setShowAuthModal(true); setAuthMode("signin"); }}
          style={styles.signInBtn}
          aria-label="Sign in"
        >
          Sign in
        </button>
      )}

      {/* My Suites button (signed in) */}
      {supabase && user && (
        <button onClick={() => navigateTo("dashboard")} style={styles.mySuitesBtn} className="sg-auth-btn">
          My Suites
        </button>
      )}

      {currentPage === "dashboard" ? (
        <Dashboard
          suites={dashboardSuites}
          loading={dashboardLoading}
          error={dashboardError}
          onOpen={handleOpenSuite}
          onNavigateHome={() => navigateTo("home")}
        />
      ) : (

      <main style={styles.main}>
        {/* Header */}
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
            AI-assisted QA test suite generation for any website — crawl the UI, get structured, downloadable test cases in minutes.
          </p>
        </header>

        {/* ── Form card (idle + error) or URL strip (active/done) ── */}
        {phase === "idle" || phase === "error" ? (
          <div style={styles.card}>
            <form onSubmit={handleCrawl} style={styles.form}>
              <div className="sg-url-row" style={styles.urlRow}>
                <div style={styles.urlInputWrap}>
                  <span style={styles.urlPrefix}>https://</span>
                  <input
                    type="text"
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    placeholder="example.com"
                    style={styles.urlInput}
                    autoFocus
                    required
                    aria-label="Website URL to crawl"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!url.trim()}
                  className="sg-gen-btn"
                  style={{ ...styles.generateBtn, ...(!url.trim() ? styles.btnDisabled : {}) }}
                >
                  Crawl Site
                </button>
              </div>

              {/* API key row */}
              <div style={styles.apiKeyRow}>
                <div style={styles.urlInputWrap}>
                  <span style={styles.urlPrefix}>API Key</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="sk-ant-api03-…"
                    style={styles.urlInput}
                    autoComplete="off"
                    aria-label="Anthropic API key"
                  />
                </div>
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.apiKeyLink}
                >
                  Get key ↗
                </a>
              </div>

              <button
                type="button"
                onClick={() => setShowAuth(v => !v)}
                style={styles.authToggle}
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
                    autoComplete="username"
                    aria-label="Username"
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="Password"
                    style={styles.authInput}
                    autoComplete="current-password"
                    aria-label="Password"
                  />
                </div>
              )}
            </form>
          </div>
        ) : (
          /* Compact URL strip shown during active phases */
          <div style={{ ...styles.card, padding: "12px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <span style={{ fontSize: 11, color: "#666", flexShrink: 0 }}>
                {phase === "crawling" ? "Crawling" : "Crawled"}
              </span>
              <span style={{ fontSize: 13, color: "#B0A0D0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {submittedUrl}
              </span>
            </div>
            {!isActive && (
              <button onClick={handleReset} style={styles.newBtn}>
                Start over
              </button>
            )}
          </div>
        )}

        {/* ── Step indicators ── */}
        {phase !== "idle" && phase !== "error" && (
          <div style={styles.progressCard} role="status" aria-live="polite">
            <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 11 }}>
              {STEPS.map((step, i) => {
                const state = stepStates[i]; // "done" | "active" | "pending"
                return (
                  <li key={step.id} style={styles.stepRow}>
                    <div style={{
                      ...styles.stepDot,
                      ...(state === "done"    ? styles.stepDotDone    : {}),
                      ...(state === "active"  ? styles.stepDotActive  : {}),
                      ...(state === "pending" ? styles.stepDotPending : {}),
                    }}>
                      {state === "done" ? "✓" : step.icon}
                    </div>
                    <span style={{
                      ...styles.stepLabel,
                      ...(state === "active"  ? { color: "#E2C4FF", fontWeight: 600 } : {}),
                      ...(state === "pending" ? { color: "#555" } : {}),
                    }}>
                      {step.label}
                      {state === "active" && <Spinner />}
                    </span>
                  </li>
                );
              })}
            </ol>
            {isActive && (
              <button onClick={handleCancel} style={styles.cancelBtn}>
                Cancel
              </button>
            )}
          </div>
        )}

        {/* ── Error card ── */}
        {phase === "error" && (
          <div style={styles.errorCard} role="alert" aria-live="assertive">
            <span style={styles.errorIcon}>⚠</span>
            <div style={{ flex: 1 }}>
              <strong style={{ color: "#FF6B6B" }}>Something went wrong</strong>
              <p style={styles.errorText}>{error}</p>
            </div>
            <button onClick={handleReset} style={styles.retryBtn}>Try Again</button>
          </div>
        )}

        {/* ── Architecture card (crawled → done) ── */}
        {crawlData && ["crawled", "generating", "done"].includes(phase) && (
          <SiteArchitectureCard crawlData={crawlData} />
        )}

        {/* ── Generate button (crawled phase only) ── */}
        {phase === "crawled" && (
          <div style={{ marginBottom: 16, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <button
              onClick={handleGenerate}
              disabled={!apiKey.trim()}
              style={{
                background: apiKey.trim() ? "linear-gradient(135deg, #7C3AED, #5B21B6)" : "rgba(124,58,237,0.2)",
                color: "#fff",
                border: "none",
                borderRadius: 10,
                padding: "13px 36px",
                fontSize: 15,
                fontWeight: 600,
                cursor: apiKey.trim() ? "pointer" : "not-allowed",
                fontFamily: "inherit",
                letterSpacing: "0.01em",
                boxShadow: apiKey.trim() ? "0 0 20px rgba(124,58,237,0.35)" : "none",
                opacity: apiKey.trim() ? 1 : 0.6,
                transition: "all 0.15s",
              }}
            >
              Generate Test Suite →
            </button>
            {!apiKey.trim() && (
              <p style={{ margin: 0, fontSize: 12, color: "#777" }}>
                Enter your{" "}
                <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" style={{ color: "#9070C0" }}>
                  Anthropic API key
                </a>
                {" "}above to generate
              </p>
            )}
          </div>
        )}

        {/* ── Test suite viewer (done phase) ── */}
        {phase === "done" && testSuiteData && (
          <TestSuiteViewer
            testSuite={testSuiteData}
            crawlData={crawlData}
            onDownloadXlsx={handleDownloadXlsx}
            isDownloading={isDownloading}
            suiteId={suiteId}
            onCopyLink={handleCopyLink}
            linkCopied={linkCopied}
            canEdit={!!(suiteId && user && suiteOwnerId && user.id === suiteOwnerId)}
            editMode={editMode}
            editedSuite={editedSuite}
            isSaving={isSaving}
            saveError={saveError}
            onEnterEdit={handleEnterEdit}
            onCancelEdit={handleCancelEdit}
            onSaveEdit={handleSaveEdit}
            onTestCaseChange={handleTestCaseChange}
          />
        )}

        {/* ── How it works (idle only) ── */}
        {phase === "idle" && (
          <div className="sg-how-grid" style={styles.howItWorks}>
            {[
              { icon: "🔍", title: "Smart Discovery",  desc: "Reads sitemap.xml to get a complete URL inventory before crawling. Falls back to link-following for sites without a sitemap." },
              { icon: "🤖", title: "AI Generation",    desc: "Claude generates test cases grounded in the actual UI — real field names, real interactions, template-aware for repeated page types." },
              { icon: "📊", title: "Inline + Export",  desc: "Browse test cases right in the browser, then export to a formatted .xlsx with a Dashboard, status dropdowns, and color coding." },
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

      )} {/* end dashboard/home conditional */}

      {/* Footer */}
      <footer style={styles.footer}>
        <a href="https://topnotchqa.com" target="_blank" rel="noopener noreferrer" style={styles.footerLink}>
          Need a human QA team? TopNotch QA offers professional testing services →
        </a>
        <p style={styles.footerCopy}>© {new Date().getFullYear()} SuiteGen</p>
      </footer>

      {/* Auth modal */}
      {showAuthModal && supabase && (
        <AuthModal
          mode={authMode}
          onModeChange={setAuthMode}
          onClose={() => setShowAuthModal(false)}
          onSuccess={() => setShowAuthModal(false)}
        />
      )}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
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
  githubLink: {
    position: "fixed",
    top: 16,
    right: 20,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 6,
    color: "#999",
    fontSize: 13,
    textDecoration: "none",
    padding: "6px 12px",
    borderRadius: 8,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    transition: "color 0.15s, background 0.15s",
  },
  main: {
    position: "relative",
    zIndex: 1,
    maxWidth: 880,
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

  // Form card
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
  apiKeyRow: {
    display: "flex",
    gap: 10,
    alignItems: "center",
  },
  apiKeyLink: {
    fontSize: 12,
    color: "#9070C0",
    textDecoration: "none",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
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
    padding: "20px 24px",
    marginBottom: 16,
  },
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

  // Architecture card
  archCard: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 14,
    padding: "18px 24px",
    marginBottom: 12,
  },

  // Stat (shared with architecture card and header)
  stat: { display: "flex", flexDirection: "column", gap: 2 },
  statValue: { fontSize: 18, fontWeight: 700, color: "#E2C4FF" },
  statLabel: { fontSize: 11, color: "#666", textTransform: "uppercase", letterSpacing: "0.05em" },

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

  // Shared buttons
  newBtn: {
    background: "none",
    border: "none",
    color: "#777",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    flexShrink: 0,
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
  howIcon:  { fontSize: 22, marginBottom: 10 },
  howTitle: { fontSize: 13, fontWeight: 600, color: "#D0C0F0", margin: "0 0 6px" },
  howDesc:  { fontSize: 12, color: "#888", lineHeight: 1.6, margin: 0 },

  // Auth modal
  modalOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.7)",
    backdropFilter: "blur(4px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
  },
  modalPanel: {
    background: "#13111F",
    border: "1px solid rgba(192,132,252,0.2)",
    borderRadius: 18,
    padding: "28px 24px",
    maxWidth: 380,
    width: "calc(100% - 48px)",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  authTabs: {
    display: "flex",
    background: "rgba(255,255,255,0.05)",
    borderRadius: 10,
    padding: 3,
    gap: 3,
  },
  authTab: {
    flex: 1,
    background: "none",
    border: "none",
    color: "#888",
    fontSize: 13,
    fontWeight: 600,
    padding: "7px 12px",
    borderRadius: 8,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "background 0.15s, color 0.15s",
  },
  authTabActive: {
    background: "rgba(124,58,237,0.3)",
    color: "#E2C4FF",
  },
  oauthBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 9,
    color: "#D0C0F0",
    fontSize: 13,
    fontWeight: 500,
    padding: "10px 16px",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "background 0.15s",
    width: "100%",
  },
  orDivider: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  orDividerLine: {
    flex: 1,
    height: 1,
    background: "rgba(255,255,255,0.08)",
    display: "block",
  },
  orDividerText: {
    fontSize: 11,
    color: "#555",
    flexShrink: 0,
  },

  // Header auth controls
  userPill: {
    position: "fixed",
    top: 16,
    right: 120,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 12,
    color: "#B0A0D0",
    padding: "6px 12px",
    borderRadius: 8,
    background: "rgba(124,58,237,0.1)",
    border: "1px solid rgba(192,132,252,0.2)",
  },
  signInBtn: {
    position: "fixed",
    top: 16,
    right: 120,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 6,
    color: "#999",
    fontSize: 13,
    padding: "6px 12px",
    borderRadius: 8,
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "color 0.15s, background 0.15s",
  },

  footer: {
    position: "relative",
    zIndex: 1,
    textAlign: "center",
    padding: "20px 24px 32px",
  },
  footerLink: {
    fontSize: 12,
    color: "#666",
    textDecoration: "none",
    transition: "color 0.15s",
  },
  footerCopy: {
    fontSize: 11,
    color: "#444",
    margin: "8px 0 0",
  },

  // My Suites button
  mySuitesBtn: {
    position: "fixed",
    top: 16,
    right: 240,
    zIndex: 10,
    display: "flex",
    alignItems: "center",
    gap: 6,
    color: "#C084FC",
    fontSize: 13,
    padding: "6px 12px",
    borderRadius: 8,
    background: "rgba(124,58,237,0.1)",
    border: "1px solid rgba(192,132,252,0.25)",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "color 0.15s, background 0.15s",
  },

  // Edit mode buttons (viewer header)
  editBtn: {
    background: "rgba(124,58,237,0.15)",
    border: "1px solid rgba(192,132,252,0.3)",
    color: "#C084FC",
    borderRadius: 8,
    padding: "8px 14px",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  saveBtn: {
    background: "linear-gradient(135deg,#7C3AED,#5B21B6)",
    border: "none",
    color: "#fff",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },
  cancelEditBtn: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#888",
    borderRadius: 8,
    padding: "8px 14px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
  },

  // Inline edit controls
  editInput: {
    flex: 1,
    background: "rgba(255,255,255,0.07)",
    border: "1px solid rgba(192,132,252,0.25)",
    borderRadius: 6,
    color: "#E2C4FF",
    padding: "5px 9px",
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  },
  editTextarea: {
    background: "rgba(255,255,255,0.07)",
    border: "1px solid rgba(192,132,252,0.25)",
    borderRadius: 6,
    color: "#E2C4FF",
    padding: "7px 9px",
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
    width: "100%",
    resize: "vertical",
    lineHeight: 1.5,
    boxSizing: "border-box",
  },
  editSelect: {
    background: "rgba(255,255,255,0.07)",
    border: "1px solid rgba(192,132,252,0.25)",
    borderRadius: 6,
    color: "#E2C4FF",
    padding: "5px 9px",
    fontSize: 13,
    fontFamily: "inherit",
    outline: "none",
  },

  // Dashboard
  dashboardWrap: {
    position: "relative",
    zIndex: 1,
    maxWidth: 880,
    margin: "0 auto",
    padding: "64px 24px 80px",
  },
  dashboardHeader: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 28,
  },
  dashboardBackBtn: {
    background: "none",
    border: "none",
    color: "#888",
    fontSize: 13,
    cursor: "pointer",
    fontFamily: "inherit",
    padding: 0,
  },
  dashboardTitle: {
    fontSize: 20,
    fontWeight: 700,
    color: "#D0C0F0",
    margin: 0,
  },
  dashboardTable: {
    display: "flex",
    flexDirection: "column",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 12,
    overflow: "hidden",
  },
  dashboardRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "14px 20px",
    background: "rgba(255,255,255,0.02)",
  },
  dashboardSiteName: {
    fontSize: 13,
    fontWeight: 600,
    color: "#D0C0F0",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  dashboardMeta: {
    fontSize: 11,
    color: "#555",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  dashboardDate: {
    fontSize: 11,
    color: "#666",
    flexShrink: 0,
    minWidth: 80,
    textAlign: "right",
  },
  dashboardActionBtn: {
    background: "rgba(124,58,237,0.15)",
    border: "1px solid rgba(192,132,252,0.25)",
    color: "#C084FC",
    borderRadius: 7,
    padding: "6px 14px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
  dashboardDownloadLink: {
    background: "none",
    border: "1px solid rgba(255,255,255,0.1)",
    color: "#888",
    borderRadius: 7,
    padding: "6px 10px",
    fontSize: 12,
    cursor: "pointer",
    fontFamily: "inherit",
    flexShrink: 0,
    textDecoration: "none",
    whiteSpace: "nowrap",
  },
};

// ── Global styles injection ───────────────────────────────────────────────────
const styleEl = document.createElement("style");
styleEl.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&display=swap');
  * { box-sizing: border-box; }
  body { margin: 0; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
  }
  @media (max-width: 600px) {
    .sg-how-grid { grid-template-columns: 1fr !important; }
    .sg-url-row  { flex-direction: column !important; }
    .sg-gen-btn  { padding: 12px 24px !important; width: 100% !important; }
    .sg-github span { display: none !important; }
    .sg-github { padding: 6px 8px !important; gap: 0 !important; }
    .sg-auth-btn { right: 72px !important; }
  }
`;
document.head.appendChild(styleEl);
