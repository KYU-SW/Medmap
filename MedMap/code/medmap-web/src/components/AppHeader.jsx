export default function AppHeader({ step = 0, total = 3 }) {
  const dots = Array.from({ length: total }, (_, i) => i < step)
  return (
    <header className="app-header">
      <span className="app-header__brand">MedMap</span>
      <div className="app-header__progress" aria-label={`추가 확인 ${step} / ${total}`}>
        <span>추가 확인</span>
        <span className="app-header__dots" aria-hidden="true">
          {dots.map((filled, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {i > 0 && <span className="progress-dash" />}
              <span className="progress-dot" data-testid="progress-dot" data-filled={String(filled)} />
            </span>
          ))}
        </span>
        <span>{step} / {total}</span>
      </div>
    </header>
  )
}
