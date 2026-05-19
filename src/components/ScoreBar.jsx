export default function ScoreBar({ label, value }) {
  const v = Math.min(100, Math.max(0, Number(value) || 0));
  const level = v >= 85 ? "high" : v >= 65 ? "mid" : "low";
  const display = typeof value === "number" && value % 1 !== 0 ? value.toFixed(1) : v;
  return (
    <div className={`score-bar ${level}`}>
      <div className="score-bar-head">
        <span className="score-bar-label">{label}</span>
        <span className="score-bar-value">{display}%</span>
      </div>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}
