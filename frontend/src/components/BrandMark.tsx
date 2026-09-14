export default function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark${compact ? ' brand-mark--compact' : ''}`} aria-label="Pizza Pizza Eyes">
      <div className="brand-mark-main">
        <span className="brand-pizza brand-pizza--a">PIZZA</span>
        <span className="brand-eye" aria-hidden="true" title="olho">
          <svg viewBox="0 0 24 24" width="1em" height="1em" fill="none">
            <ellipse cx="12" cy="12" rx="9" ry="5.5" stroke="currentColor" strokeWidth="2.2" />
            <circle cx="12" cy="12" r="2.6" fill="currentColor" />
          </svg>
        </span>
        <span className="brand-pizza brand-pizza--b">PIZZA</span>
      </div>
      <div className="brand-mark-sub">
        <span>E</span>
        <span>Y</span>
        <span>E</span>
        <span>S</span>
      </div>
    </div>
  )
}
