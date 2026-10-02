export default function ChoiceButton({ label, selected = false, onClick, disabled = false }) {
  return (
    <button type="button" className="button choice" aria-pressed={selected} onClick={onClick} disabled={disabled}>
      {label}
    </button>
  )
}
