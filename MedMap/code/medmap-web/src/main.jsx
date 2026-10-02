import './styles/plain.css'
import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import DoctorApp from './doctor/DoctorApp.jsx'
import HandoffApp from './handoff/HandoffApp.jsx'

// 진입 분기: 해시 없음 = 기존 환자 앱(그대로), #/handoff = 의사 인계용 intake, #/doctor = 의사 화면.
export function routeOf(hash) {
  if (hash === '#/doctor') return 'doctor'
  if (hash === '#/handoff') return 'handoff'
  return 'patient'
}

export function Root() {
  const [route, setRoute] = useState(() => routeOf(window.location.hash))
  useEffect(() => {
    const onHash = () => setRoute(routeOf(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  if (route === 'doctor') return <DoctorApp key="doctor" />
  if (route === 'handoff') return <HandoffApp key="handoff" />
  return <App key="patient" />
}

const container = document.getElementById('root')
if (container) {
  createRoot(container).render(
    <StrictMode>
      <Root />
    </StrictMode>,
  )
}
