import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  annotateBatchUpload,
  annotateDocumentStructured,
  annotateNameFull,
  fetchDuplicates,
  fetchHistory,
  fetchKnowledgeStats,
  fetchMe,
  healthCheck,
  learnName,
  login,
  normalizeName,
  setToken,
  speechToName,
  validateCorrection,
} from "./api/client";
import ScoreBar from "./components/ScoreBar";
import { useMicrophoneRecorder } from "./hooks/useMicrophoneRecorder";
import "./App.css";

const TABS = [
  { id: "standardize", label: "Standardiser", icon: "✦" },
  { id: "document", label: "Document long", icon: "📄" },
  { id: "batch", label: "Import batch", icon: "📊" },
  { id: "duplicates", label: "Doublons", icon: "⚠" },
  { id: "admin", label: "Validation", icon: "✓" },
];

function SearchIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3-3" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8" />
    </svg>
  );
}

function ResultPanel({ result, resultStatus, editingResult, resultEdit, setResultEdit, onEdit, onSave, onValidate, onReject }) {
  if (!result || resultStatus === "rejected") return null;

  return (
    <div className={`result-card ${resultStatus === "validated" ? "validated" : ""}`}>
      <div className="result-card-header">
        <div>
          <span className="result-label">Identité annotée</span>
          <h3 className="result-title">
            {editingResult ? (
              <input
                className="result-edit-input"
                value={resultEdit.normalized}
                onChange={(e) => setResultEdit((f) => ({ ...f, normalized: e.target.value }))}
              />
            ) : (
              result.normalized
            )}
          </h3>
          {result.input !== result.normalized && <p className="result-original">Original : {result.input}</p>}
        </div>
        {(editingResult ? resultEdit.arabic : result.arabic_name) && (
          <p className="result-arabic arabic">{editingResult ? resultEdit.arabic : result.arabic_name}</p>
        )}
      </div>

      <div className="score-grid">
        <ScoreBar label="Confiance IA" value={result.confidence} />
        <ScoreBar label="Qualité annotation" value={result.annotation_quality ?? result.confidence} />
        <ScoreBar label="Risque doublon" value={result.duplicate_probability ?? 0} />
        {result.phonetic_score != null && <ScoreBar label="Score phonétique" value={result.phonetic_score} />}
      </div>

      {result.linguistic_tags?.length > 0 && (
        <div className="tag-row">
          {result.linguistic_tags.map((t) => (
            <span key={t} className="lang-tag">
              {t}
            </span>
          ))}
        </div>
      )}

      {result.ai_explanation && <p className="ai-explanation">{result.ai_explanation}</p>}

      {result.near_duplicates?.length > 0 && (
        <div className="dup-alert">
          <strong>Alertes similarité</strong>
          <ul>
            {result.near_duplicates.slice(0, 3).map((d) => (
              <li key={d.name}>
                {d.name} — {d.similarity_score?.toFixed?.(0) ?? d.similarity_score}%
                {d.likely_duplicate && " (doublon probable)"}
              </li>
            ))}
          </ul>
        </div>
      )}

      {resultStatus === "validated" ? (
        <span className="result-badge-ok">✓ Validé & mémorisé localement</span>
      ) : (
        <div className="result-actions">
          <button type="button" className="result-btn edit" onClick={onEdit}>
            Modifier
          </button>
          {editingResult && (
            <button type="button" className="result-btn save" onClick={onSave}>
              Enregistrer
            </button>
          )}
          <button type="button" className="result-btn ok" onClick={onValidate}>
            Valider
          </button>
          <button type="button" className="result-btn no" onClick={onReject}>
            Rejeter
          </button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("standardize");
  const [name, setName] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState(null);
  const [knowledge, setKnowledge] = useState(null);
  const [showLogin, setShowLogin] = useState(false);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ normalized: "", arabic: "" });
  const [learnMessage, setLearnMessage] = useState(null);
  const [editingResult, setEditingResult] = useState(false);
  const [resultEdit, setResultEdit] = useState({ normalized: "", arabic: "" });
  const [resultStatus, setResultStatus] = useState(null);
  const [docText, setDocText] = useState("");
  const [docResult, setDocResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [duplicates, setDuplicates] = useState(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);

  const { isRecording, startRecording, stopRecording } = useMicrophoneRecorder();

  const logout = useCallback(() => {
    setToken(null);
    setLoggedIn(false);
    setHistory([]);
  }, []);

  const loadHistory = useCallback(async () => {
    if (!loggedIn) return;
    try {
      setHistory(await fetchHistory());
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) logout();
    }
  }, [loggedIn, logout]);

  useEffect(() => {
    healthCheck()
      .then((h) => {
        setHealth(h);
        return fetchKnowledgeStats().catch(() => null);
      })
      .then(setKnowledge)
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setAuthReady(true);
      return;
    }
    fetchMe()
      .then(() => setLoggedIn(true))
      .catch(() => logout())
      .finally(() => setAuthReady(true));
  }, [logout]);

  useEffect(() => {
    if (authReady && loggedIn) loadHistory();
  }, [authReady, loggedIn, loadHistory]);

  const applyResult = (data) => {
    setResult(data);
    setName(data.normalized);
    setResultStatus("pending");
    setEditingResult(false);
    setLearnMessage(null);
    if (loggedIn) loadHistory();
  };

  const handleNormalize = async (inputName) => {
    const query = (inputName ?? name).trim();
    if (!query || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await annotateNameFull(query, null).catch(() => normalizeName(query, null));
      applyResult(data);
      inputRef.current?.focus();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDocumentAnalyze = async () => {
    if (!docText.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      setDocResult(await annotateDocumentStructured(docText, null, 80));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    try {
      setBatchResult(await annotateBatchUpload(file, null));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const loadDuplicates = async () => {
    setLoading(true);
    setError(null);
    try {
      setDuplicates(await fetchDuplicates(82));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "duplicates" && !duplicates) loadDuplicates();
  }, [tab]);

  const handleMicClick = async () => {
    if (loading) return;
    if (isRecording) {
      setLoading(true);
      setError(null);
      try {
        const { file } = await stopRecording();
        if (file.size < 500) throw new Error("Enregistrement trop court.");
        applyResult(await speechToName(file, null));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    } else {
      setError(null);
      await startRecording();
    }
  };

  const handleResultValidate = async () => {
    if (!result) return;
    const norm = editingResult ? resultEdit.normalized.trim() : result.normalized;
    const ar = editingResult ? resultEdit.arabic.trim() : result.arabic_name || "";
    try {
      const res = await learnName(result.input, norm, ar);
      setResultStatus("validated");
      setLearnMessage(res.message);
      setResult((r) => ({ ...r, normalized: norm, arabic_name: ar }));
      setName(norm);
      setEditingResult(false);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const { access_token } = await login(username, password);
      setToken(access_token);
      setLoggedIn(true);
      setShowLogin(false);
      loadHistory();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="app dashboard-app">
      <nav className="top-nav gov-nav">
        <div className="nav-brand-block">
          <span className="nav-brand">N-ID</span>
          <span className="nav-sub">Annotation d&apos;identité multilingue · Mauritanie</span>
        </div>
        <div className="nav-actions">
          {health?.status === "ok" && <span className="nav-pill ok">Système actif</span>}
          {loggedIn ? (
            <button type="button" className="nav-link" onClick={logout}>
              Déconnexion
            </button>
          ) : (
            <button type="button" className="nav-link" onClick={() => setShowLogin(true)}>
              Connexion admin
            </button>
          )}
        </div>
      </nav>

      <header className="dashboard-hero">
        <p className="hero-eyebrow">FlagOS Track 3 · Long-Context Annotation</p>
        <h1>Annotation d&apos;identités · contexte long</h1>
        <p className="hero-subtitle">
          Pipeline 6 étapes : extraction → normalisation → linguistique → phonétique → regroupement →
          explication — arabe, français, hassaniya, pulaar, wolof
        </p>
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-value">{knowledge?.total_count ?? health?.knowledge?.total_count ?? "—"}</span>
            <span className="stat-label">Entrées dictionnaire</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{knowledge?.learned_count ?? "—"}</span>
            <span className="stat-label">Apprises (mémoire)</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{health?.openai_configured ? "GPT+Whisper" : "Local"}</span>
            <span className="stat-label">Moteur IA</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">v{health?.version ?? "2.0"}</span>
            <span className="stat-label">Pipeline N-ID</span>
          </div>
        </div>
      </header>

      <div className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab-btn ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="tab-icon">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      <main className="dashboard-main">
        {error && <p className="search-error global-error">{error}</p>}
        {learnMessage && <div className="learn-toast">{learnMessage}</div>}

        {tab === "standardize" && (
          <section className="panel">
            <div className="search-card">
              <h2>Annotation intelligente · nom unique</h2>
              <p className="search-card-desc">Texte ou voix → extraction → OpenAI (ICL) → phonétique → score confiance</p>
              <div className="search-row">
                <div className={`search-input-wrap ${loading ? "loading" : ""} ${isRecording ? "recording" : ""}`}>
                  <input
                    ref={inputRef}
                    type="text"
                    className="search-input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleNormalize())}
                    placeholder="Mohamed O Ahmed, محمد ولد أحمد, Mouhamed O Ahmed…"
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className={`mic-in-input ${isRecording ? "active" : ""}`}
                    onClick={handleMicClick}
                    disabled={loading}
                  >
                    <MicIcon />
                  </button>
                </div>
                <button
                  type="button"
                  className="search-submit"
                  onClick={() => handleNormalize()}
                  disabled={loading || !name.trim()}
                >
                  {loading ? <span className="spinner" /> : <SearchIcon />}
                </button>
              </div>
            </div>

            <ResultPanel
              result={result}
              resultStatus={resultStatus}
              editingResult={editingResult}
              resultEdit={resultEdit}
              setResultEdit={setResultEdit}
              onEdit={() => {
                setEditingResult(true);
                setResultEdit({ normalized: result.normalized, arabic: result.arabic_name || "" });
              }}
              onSave={() => {
                setResult({ ...result, normalized: resultEdit.normalized, arabic_name: resultEdit.arabic });
                setEditingResult(false);
              }}
              onValidate={handleResultValidate}
              onReject={() => setResultStatus("rejected")}
            />
          </section>
        )}

        {tab === "document" && (
          <section className="panel">
            <h2>Analyse document administratif long</h2>
            <p className="panel-desc">Collez une liste de citoyens — détection des noms, incohérences et clusters d&apos;identité</p>
            <textarea
              className="doc-textarea"
              value={docText}
              onChange={(e) => setDocText(e.target.value)}
              placeholder={"Mohamed O Ahmed\nمحمد ولد أحمد\nMouhamed O Ahmed\nRamata dink\n…"}
              rows={12}
            />
            <button type="button" className="primary-btn" onClick={handleDocumentAnalyze} disabled={loading}>
              {loading ? "Analyse en cours…" : "Annoter le document"}
            </button>

            {docResult && (
              <div className="doc-results">
                <div className="summary-cards">
                  <div className="summary-card">
                    <strong>{docResult.entities?.length ?? docResult.total_annotated ?? 0}</strong> entités
                  </div>
                  <div className="summary-card warn">
                    <strong>{docResult.duplicate_clusters?.length ?? docResult.summary?.duplicate_alerts ?? 0}</strong> clusters
                  </div>
                  <div className="summary-card">
                    <strong>{docResult.overall_quality_score ?? docResult.summary?.average_confidence ?? 0}%</strong> qualité globale
                  </div>
                </div>

                {docResult.document_summary && <p className="doc-summary">{docResult.document_summary}</p>}

                {(docResult.duplicate_clusters ?? docResult.identity_clusters)?.length > 0 && (
                  <div className="cluster-box">
                    <h3>duplicate_clusters</h3>
                    {(docResult.duplicate_clusters ?? docResult.identity_clusters).map((c, i) => (
                      <div key={c.group_id ?? i} className="cluster-item">
                        <span>
                          {c.group_id && <strong>{c.group_id} — </strong>}
                          {(c.members ?? c.variants)?.join(" ↔ ")}
                        </span>
                        {(c.reasoning || c.avg_similarity) && (
                          <p className="cluster-reason">{c.reasoning || `${c.avg_similarity}% similarité`}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <div className="batch-table-wrap">
                  <table className="batch-table">
                    <thead>
                      <tr>
                        <th>Groupe</th>
                        <th>Original</th>
                        <th>Normalisé</th>
                        <th>Langue</th>
                        <th>Conf.</th>
                        <th>Phonét.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(docResult.entities ?? docResult.annotations)?.map((e, i) => (
                        <tr key={i} className={(e.duplicate_group_id || e.duplicate_probability >= 75) ? "row-warn" : ""}>
                          <td>{e.duplicate_group_id || e.line_number || "—"}</td>
                          <td>{e.original ?? e.input}</td>
                          <td>{e.normalized}</td>
                          <td>{e.language_detected ?? "—"}</td>
                          <td>{e.confidence_score ?? e.confidence}%</td>
                          <td>{e.phonetic_similarity ?? e.duplicate_probability ?? 0}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        )}

        {tab === "batch" && (
          <section className="panel">
            <h2>Import batch · CSV / Excel / texte</h2>
            <p className="panel-desc">Traitement massif avec annotation automatique et détection de doublons</p>
            <label className="upload-zone">
              <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,.xlsx,.xls,.json" onChange={handleBatchUpload} />
              <span>{loading ? "Traitement…" : "Glisser ou cliquer pour importer"}</span>
            </label>

            {batchResult && (
              <div className="doc-results">
                <p className="batch-meta">
                  {batchResult.total} noms · confiance moy. {batchResult.summary?.average_confidence}% ·{" "}
                  {batchResult.summary?.duplicate_alerts} alertes
                  {batchResult.file_metadata?.filename && ` · ${batchResult.file_metadata.filename}`}
                </p>
                <div className="batch-table-wrap">
                  <table className="batch-table">
                    <thead>
                      <tr>
                        <th>Original</th>
                        <th>Normalisé</th>
                        <th>Arabe</th>
                        <th>Conf.</th>
                        <th>Doublon</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchResult.annotations?.slice(0, 100).map((a, i) => (
                        <tr key={i} className={a.duplicate_probability >= 75 ? "row-warn" : ""}>
                          <td>{a.input}</td>
                          <td>{a.normalized}</td>
                          <td className="arabic">{a.arabic_name}</td>
                          <td>{a.confidence}%</td>
                          <td>{a.duplicate_probability ?? 0}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        )}

        {tab === "duplicates" && (
          <section className="panel">
            <div className="panel-head-row">
              <h2>Détection doublons d&apos;identité</h2>
              <button type="button" className="secondary-btn" onClick={loadDuplicates} disabled={loading}>
                Actualiser
              </button>
            </div>
            {duplicates && (
              <>
                <p className="panel-desc">
                  {duplicates.count} paires · {duplicates.high_risk_count ?? 0} risque élevé
                </p>
                <div className="dup-list">
                  {duplicates.duplicates?.map((d, i) => (
                    <div key={i} className="dup-card">
                      <div className="dup-names">
                        <span>{d.citizen_1?.name}</span>
                        <span className="dup-arrow">↔</span>
                        <span>{d.citizen_2?.name}</span>
                      </div>
                      <ScoreBar label="Probabilité doublon" value={d.duplicate_probability ?? d.similarity_score} />
                      <p className="ai-explanation">{d.ai_explanation}</p>
                      <span className={`rec-badge ${d.recommendation}`}>{d.recommendation}</span>
                    </div>
                  ))}
                  {duplicates.count === 0 && <p>Aucun doublon détecté au seuil actuel.</p>}
                </div>
              </>
            )}
          </section>
        )}

        {tab === "admin" && (
          <section className="panel admin-panel-full">
            <h2>Validation humaine & mémoire adaptative</h2>
            {!loggedIn ? (
              <p className="panel-desc">Connectez-vous pour valider les corrections et enrichir le dictionnaire local.</p>
            ) : history.length === 0 ? (
              <p className="panel-desc">Aucun historique pour le moment.</p>
            ) : (
              <div className="history-table-wrap">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Entrée</th>
                      <th>Normalisé</th>
                      <th>Arabe</th>
                      <th>Conf.</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((r) => (
                      <tr key={r.id}>
                        <td>{r.input_name}</td>
                        <td>
                          {editingId === r.id ? (
                            <input
                              className="edit-input"
                              value={editForm.normalized}
                              onChange={(e) => setEditForm((f) => ({ ...f, normalized: e.target.value }))}
                            />
                          ) : (
                            r.normalized_name
                          )}
                        </td>
                        <td className="arabic">
                          {editingId === r.id ? (
                            <input
                              className="edit-input"
                              value={editForm.arabic}
                              onChange={(e) => setEditForm((f) => ({ ...f, arabic: e.target.value }))}
                            />
                          ) : (
                            r.arabic_name
                          )}
                        </td>
                        <td>{r.confidence}%</td>
                        <td>
                          {r.validated === 0 && (
                            <>
                              {editingId !== r.id && (
                                <button
                                  type="button"
                                  className="btn-xs"
                                  onClick={() => {
                                    setEditingId(r.id);
                                    setEditForm({
                                      normalized: r.normalized_name || "",
                                      arabic: r.arabic_name || "",
                                    });
                                  }}
                                >
                                  Modifier
                                </button>
                              )}
                              <button
                                type="button"
                                className="btn-xs ok"
                                onClick={async () => {
                                  try {
                                    const res = await validateCorrection(
                                      r.id,
                                      true,
                                      editingId === r.id ? editForm.normalized : r.normalized_name,
                                      editingId === r.id ? editForm.arabic : r.arabic_name,
                                      null
                                    );
                                    setEditingId(null);
                                    if (res?.message) setLearnMessage(res.message);
                                    loadHistory();
                                  } catch (e) {
                                    setError(e.message);
                                  }
                                }}
                              >
                                Valider
                              </button>
                            </>
                          )}
                          {r.validated === 1 && "✓"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="dashboard-footer">
        <p>
          N-ID · Gouvernance numérique · État civil · Santé · Banques · Anti-fraude ·{" "}
          <em>FlagOS Open Computing Global Challenge — Track 3</em>
        </p>
      </footer>

      {showLogin && (
        <div className="modal-overlay" onClick={() => setShowLogin(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleLogin}>
            <h3>Connexion administrateur</h3>
            <input type="text" placeholder="Utilisateur" value={username} onChange={(e) => setUsername(e.target.value)} />
            <input
              type="password"
              placeholder="Mot de passe"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="submit" className="modal-submit">
              Se connecter
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
