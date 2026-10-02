export default function Notice({ message, onRetry, onRestart, pending = false }) {
  if (!message) return null
  return (
    <div className="notice" role="alert">
      <p className="notice__title">{message.title}</p>
      {message.body && <p className="notice__body">{message.body}</p>}
      {message.action === 'retry' && onRetry && (
        <button type="button" className="button" onClick={onRetry} disabled={pending}>다시 시도</button>
      )}
      {message.action === 'restart' && onRestart && (
        <button type="button" className="button" onClick={onRestart} disabled={pending}>처음부터 다시</button>
      )}
    </div>
  )
}
