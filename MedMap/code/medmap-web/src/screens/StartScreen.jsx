export default function StartScreen({ ready = false, checking = false, onStart }) {
  return (
    <main className="start">
      <h1 className="start__title">MedMap</h1>
      <p className="start__lede">증상을 한 번에 판단하지 않습니다. 확인이 필요한 정보를 하나씩 좁혀갑니다.</p>
      <button className="button button--primary" type="button" onClick={onStart} disabled={!ready}>
        시작하기
      </button>
      {!ready && !checking && (
        <p className="start__notice" role="status">준비 중입니다. 잠시 후 다시 시도해 주세요.</p>
      )}
      <p className="start__disclaimer">의료 행위가 아니며 진료를 대신하지 않습니다.</p>
    </main>
  )
}
