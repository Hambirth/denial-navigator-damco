"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function statusClass(status) {
  if (status === "matched") return "status matched";
  if (status === "mismatched") return "status mismatched";
  return "status missing";
}

function compactText(value) {
  return value || "Not supplied";
}

function reasoningLabel(result) {
  if (result?.reasoning_mode === "llm") return "LLM";
  return "Deterministic fallback";
}

export default function Home() {
  const [scenarios, setScenarios] = useState([]);
  const [scenarioId, setScenarioId] = useState("valid-authorization");
  const [scenario, setScenario] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function loadScenarios() {
      try {
        const response = await fetch(`${API_BASE}/api/scenarios`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load scenarios");
        setScenarios(data.scenarios);
      } catch (err) {
        setError(err.message);
      }
    }
    loadScenarios();
  }, []);

  useEffect(() => {
    async function loadScenario() {
      setError("");
      setResult(null);
      try {
        const response = await fetch(`${API_BASE}/api/scenarios/${scenarioId}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load scenario");
        setScenario(data);
      } catch (err) {
        setError(err.message);
      }
    }
    loadScenario();
  }, [scenarioId]);

  const claimFields = useMemo(() => result?.extracted_evidence?.claim?.fields || [], [result]);
  const authFields = useMemo(() => result?.extracted_evidence?.authorization?.fields || [], [result]);

  async function analyze() {
    if (!scenario) return;
    setIsLoading(true);
    setError("");
    setResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/analyze-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eob_text: scenario.eob_text,
          authorization_text: scenario.authorization_text,
          use_llm_reasoning: false,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Analysis failed");
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Damco AI Engineer Challenge</p>
          <h1>Denial Navigator AI</h1>
          <p className="subhead">Synthetic CO-197 workflow from source text to grounded structured recommendation.</p>
        </div>
      </section>

      <section className="workspace">
        <aside className="panel">
          <label htmlFor="scenario">Scenario</label>
          <select id="scenario" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>
            {scenarios.map((item) => (
              <option key={item.id} value={item.id}>{item.title}</option>
            ))}
          </select>
          <p className="muted">{scenario?.description || "Loading synthetic scenario..."}</p>
          <button onClick={analyze} disabled={isLoading || !scenario}>{isLoading ? "Analyzing..." : "Analyze Denial"}</button>
        </aside>

        <section className="panel sourcePanel">
          <p className="stage">Source Documents</p>
          <h2>Source EOB</h2>
          <pre>{compactText(scenario?.eob_text)}</pre>
        </section>

        <section className="panel sourcePanel">
          <p className="stage">Source Documents</p>
          <h2>Source Authorization</h2>
          <pre>{compactText(scenario?.authorization_text)}</pre>
        </section>
      </section>

      {error && <section className="error">{String(error)}</section>}

      {result && (
        <section className="results">
          <div className="resultHeader">
            <div>
              <p className="eyebrow">Structured Decision</p>
              <h2>{result.recommended_action.replace("_", " ")}</h2>
              <p className="muted">Reasoning: {reasoningLabel(result)}</p>
            </div>
            <div className="score">{Math.round(result.confidence * 100)}%</div>
          </div>

          <div className="twoCol">
            <section className="panel">
              <p className="stage">Extracted Evidence</p>
              <h3>Extracted Claim</h3>
              <dl className="fieldList">
                {claimFields.map((item) => (
                  <div key={`claim-${item.name}`}>
                    <dt>{item.name.replaceAll("_", " ")}</dt>
                    <dd>{compactText(item.value)}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="panel">
              <p className="stage">Extracted Evidence</p>
              <h3>Extracted Authorization</h3>
              {authFields.length ? (
                <dl className="fieldList">
                  {authFields.map((item) => (
                    <div key={`auth-${item.name}`}>
                      <dt>{item.name.replaceAll("_", " ")}</dt>
                      <dd>{compactText(item.value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : <p className="empty">No authorization source text supplied.</p>}
            </section>
          </div>

          <section className="panel">
            <p className="stage">Decision</p>
            <h3>Denial Summary</h3>
            <p>{result.denial.summary}</p>
            <p><strong>Root cause:</strong> {result.root_cause}</p>
            <p><strong>Human review:</strong> {result.requires_human_review ? "Required" : "Not required for demo decision"}</p>
          </section>

          <section className="panel">
            <p className="stage">Validation</p>
            <h3>Evidence Validation</h3>
            <div className="evidenceList">
              {result.evidence.map((item) => (
                <div className="evidenceRow" key={`${item.type}-${item.value}`}>
                  <span>{item.type.replaceAll("_", " ")}</span>
                  <span>{item.value}</span>
                  <span className={statusClass(item.status)}>{item.status}</span>
                </div>
              ))}
            </div>
          </section>

          <div className="twoCol">
            <section className="panel">
              <h3>Contradictions</h3>
              {result.contradictions.length ? result.contradictions.map((item) => (
                <p key={item.field}><strong>{item.field}:</strong> {item.explanation}</p>
              )) : <p className="empty">None</p>}
            </section>
            <section className="panel">
              <h3>Missing Evidence</h3>
              {result.missing_evidence.length ? (
                <ul>{result.missing_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
              ) : <p className="empty">None</p>}
            </section>
          </div>

          <section className="panel">
            <h3>Grounded Reasoning</h3>
            <p>{result.reasoning_summary}</p>
          </section>
        </section>
      )}
    </main>
  );
}
